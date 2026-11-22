import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from app.services import APIError


class MarketTrackWebTests(TestCase):
    def _login_session(self, is_staff: bool = True, email: str = "staff1@example.com"):
        session = self.client.session
        session["access_token"] = "fake-jwt-token"
        session["refresh_token"] = "fake-refresh-token"
        session["user_name"] = "staff1"
        session["user_email"] = email
        session["is_staff"] = is_staff
        session["active_group_id"] = 1
        session["_nav_mod_count"] = 0
        session["_nav_badge_ts"] = 9999999999
        session.save()

    def test_unauthenticated_redirects_to_login(self):
        for route in ("dashboard", "lists", "products", "moderation", "maintenance", "staff_manage"):
            resp = self.client.get(reverse(route))
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.url, reverse("login"))

    def test_non_staff_session_is_flushed_and_redirected(self):
        self._login_session(is_staff=False, email="comum@example.com")
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("login"))
        self.assertNotIn("access_token", self.client.session)

    @patch("app.views.login_view.login_with_api")
    def test_login_allows_staff_and_redirects_to_dashboard(self, mock_login):
        mock_login.return_value = {
            "access": "jwt-123",
            "refresh": "ref-456",
            "user": {"username": "staff1", "email": "staff1@example.com", "is_staff": True},
        }

        resp = self.client.post(
            reverse("login"),
            {"email": "staff1@example.com", "password": "secret"},
        )
        self.assertRedirects(resp, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("access_token"), "jwt-123")
        self.assertTrue(self.client.session.get("is_staff"))

    @patch("app.views.login_view.login_with_api")
    def test_login_blocks_non_staff_user(self, mock_login):
        mock_login.return_value = {
            "access": "jwt-user",
            "refresh": "ref-user",
            "user": {"username": "comum", "email": "comum@example.com", "is_staff": False},
        }
        resp = self.client.post(
            reverse("login"),
            {"email": "comum@example.com", "password": "secret"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Staff")
        self.assertNotIn("access_token", self.client.session)

    def test_public_register_redirects_to_login(self):
        resp = self.client.get(reverse("cadastro"))
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)

    @patch("app.views.google_login_view.google_login_with_api")
    @patch("app.views.google_login_view.verify_firebase_id_token")
    def test_google_login_allows_staff_users(self, mock_verify, mock_api):
        for allowed_email in (
            "staff1@example.com",
            "staff2@example.com",
            "staff3@example.com",
        ):
            self.client.session.flush()
            mock_verify.return_value = {
                "email": allowed_email,
                "display_name": "Equipe Staff",
                "photo_url": None,
                "email_verified": True,
            }
            mock_api.return_value = {
                "access": "jwt-google",
                "refresh": "ref-google",
                "user": {"username": "staff", "email": allowed_email, "is_staff": True},
            }

            resp = self.client.post(
                reverse("google_login"),
                data=json.dumps({"id_token": "valid-firebase-token"}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json().get("redirect_url"), reverse("dashboard"))
            self.assertTrue(self.client.session.get("is_staff"))

    @patch("app.views.google_login_view.google_login_with_api")
    @patch("app.views.google_login_view.verify_firebase_id_token")
    def test_google_login_blocks_non_staff_user(self, mock_verify, mock_api):
        mock_verify.return_value = {
            "email": "outro@gmail.com",
            "display_name": "Outro",
            "photo_url": None,
            "email_verified": True,
        }
        mock_api.side_effect = APIError(
            "Acesso restrito: apenas contas com permissão de Staff podem acessar o painel web.",
            status_code=403,
        )
        resp = self.client.post(
            reverse("google_login"),
            data=json.dumps({"id_token": "valid-firebase-token"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Staff", resp.json().get("error", ""))
        self.assertNotIn("access_token", self.client.session)

    def test_logout_flushes_session(self):
        self._login_session()
        resp = self.client.post(reverse("logout"))
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)

    @patch("app.services.get_markets")
    @patch("app.services.get_price_alerts")
    @patch("app.services.get_community_offers")
    @patch("app.services.get_shopping_lists")
    @patch("app.services.get_groups")
    @patch("app.services.get_users")
    def test_dashboard_period_filter_and_csv_export(
        self, mock_users, mock_groups, mock_lists, mock_offers, mock_alerts, mock_markets
    ):
        self._login_session()
        mock_users.return_value = [{"id": 1, "username": "u1"}, {"id": 2, "username": "u2"}]
        mock_groups.return_value = [{"id": 1, "name": "Família Silva"}]
        mock_lists.return_value = [{"id": 10, "name": "Compras do Mês", "budget_cents": 50000}]
        mock_offers.return_value = [
            {
                "id": 100,
                "product_name": "Café Pilão 500g",
                "market_name": "Atacadão",
                "category": "Mercearia",
                "price_cents": 1490,
                "reference_avg_cents": 1890,
                "moderation_status": "flagged",
                "created_at": "2026-11-22T12:00:00Z",
            }
        ]
        mock_alerts.return_value = [
            {
                "id": 5,
                "product_name": "Café Pilão 500g",
                "target_price_cents": 1500,
                "is_read": True,
                "created_at": "2026-11-22T10:00:00Z",
            }
        ]
        mock_markets.return_value = [{"id": 1, "name": "Atacadão", "latitude": None, "longitude": None}]

        resp = self.client.get(reverse("dashboard") + "?days=7")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Atenção imediata")
        self.assertContains(resp, "Gráficos Práticos")

        csv_resp = self.client.get(reverse("dashboard_export_csv") + "?metric=all&days=all")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp["Content-Type"])
        self.assertIn("Café Pilão 500g", csv_resp.content.decode("utf-8"))

    @patch("app.services.delete_shopping_list")
    @patch("app.services.get_shopping_list_items")
    @patch("app.services.get_group_members")
    @patch("app.services.get_shopping_list")
    @patch("app.services.get_shopping_lists")
    @patch("app.services.get_groups")
    def test_lists_and_list_detail_and_delete(
        self,
        mock_groups,
        mock_lists,
        mock_list_get,
        mock_members,
        mock_items,
        mock_delete,
    ):
        self._login_session()
        mock_groups.return_value = [{"id": 1, "name": "Casa"}]
        mock_lists.return_value = [
            {"id": 10, "name": "Churrasco", "group": 1, "budget_cents": 30000, "status": "open"}
        ]
        mock_list_get.return_value = {
            "id": 10,
            "name": "Churrasco",
            "group": 1,
            "budget_cents": 30000,
        }
        mock_members.return_value = [{"id": 50, "user_username": "Ana Paula", "is_admin": True}]
        mock_items.return_value = [
            {"id": 99, "product_name": "Picanha 1kg", "quantity": 2, "selected_price_cents": 6990}
        ]

        resp_idx = self.client.get(reverse("lists"))
        self.assertEqual(resp_idx.status_code, 200)
        self.assertContains(resp_idx, "Churrasco")

        resp_det = self.client.get(reverse("list_detail", kwargs={"list_id": 10}))
        self.assertEqual(resp_det.status_code, 200)
        self.assertContains(resp_det, "Ana Paula")
        self.assertContains(resp_det, "Picanha 1kg")

        resp_del = self.client.post(reverse("list_delete", kwargs={"list_id": 10}))
        self.assertRedirects(resp_del, reverse("lists"), fetch_redirect_response=False)
        mock_delete.assert_called_once()

    @patch("app.services.promote_product_global")
    @patch("app.services.create_product")
    @patch("app.services.delete_product")
    @patch("app.services.update_product")
    @patch("app.services.get_community_offers")
    @patch("app.services.get_product")
    @patch("app.services.get_products")
    def test_products_crud_promote_and_price_chart(
        self,
        mock_products,
        mock_product,
        mock_offers,
        mock_update,
        mock_delete,
        mock_create,
        mock_promote,
    ):
        self._login_session()
        sample_product = {
            "id": 42,
            "name": "Arroz Tio João 5kg",
            "brand": "Tio João",
            "category": "Mercearia",
            "barcode": "7893500020110",
            "status": "active",
            "is_global": False,
        }
        mock_products.return_value = [sample_product]
        mock_product.return_value = sample_product
        mock_create.return_value = {"id": 99, "name": "Feijão Camil 1kg", "is_global": True}
        mock_offers.return_value = [
            {
                "id": 1,
                "ean": "7893500020110",
                "product_name": "Arroz Tio João 5kg",
                "market_name": "Assaí",
                "price_cents": 2790,
                "discount_percent": 12,
                "created_at": "2026-11-20T15:00:00Z",
            }
        ]

        resp_list = self.client.get(reverse("products") + "?category=Mercearia")
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, "Arroz Tio João 5kg")

        resp_create = self.client.post(
            reverse("product_create"),
            {"name": "Feijão Camil 1kg", "category": "Mercearia"},
        )
        self.assertRedirects(resp_create, reverse("products"), fetch_redirect_response=False)
        mock_create.assert_called_once()

        resp_det = self.client.get(reverse("product_detail", kwargs={"product_id": 42}))
        self.assertEqual(resp_det.status_code, 200)
        self.assertContains(resp_det, "productPriceChart")
        self.assertContains(resp_det, "Promover a Global")

        resp_prom = self.client.post(reverse("product_promote", kwargs={"product_id": 42}))
        self.assertRedirects(
            resp_prom, reverse("product_detail", kwargs={"product_id": 42}), fetch_redirect_response=False
        )
        mock_promote.assert_called_once()

        self.client.post(
            reverse("product_edit", kwargs={"product_id": 42}),
            {"name": "Arroz Tio João 5kg Tipo 1", "category": "Mercearia", "status": "active"},
        )
        mock_update.assert_called_once()

        self.client.post(reverse("product_delete", kwargs={"product_id": 42}))
        mock_delete.assert_called_once()

    @patch("app.services.update_market")
    @patch("app.services.promote_product_global")
    @patch("app.services.moderate_offer")
    @patch("app.services.get_users")
    @patch("app.services.get_markets")
    @patch("app.services.get_products")
    @patch("app.services.get_community_offers")
    def test_moderation_tabs_and_actions(
        self,
        mock_offers,
        mock_products,
        mock_markets,
        mock_users,
        mock_moderate,
        mock_promote,
        mock_update_market,
    ):
        self._login_session(is_staff=True)
        mock_offers.return_value = [
            {
                "id": 77,
                "product_name": "Azeite 500ml",
                "market_name": "Carrefour",
                "price_cents": 199,
                "reference_avg_cents": 3990,
                "abuse_reports_count": 3,
                "moderation_status": "flagged",
            }
        ]
        mock_products.return_value = [
            {"id": 88, "name": "Biscoito Oreo 90g", "barcode": "7622210449283", "is_global": False}
        ]
        mock_markets.return_value = [
            {"id": 9, "name": "Supermercado Central", "city": "", "latitude": None, "longitude": None}
        ]
        mock_users.return_value = [
            {"id": 3, "username": "troll01", "email": "troll@example.com", "community_banned": True}
        ]

        r_offers = self.client.get(reverse("moderation") + "?tab=offers")
        self.assertContains(r_offers, "Azeite 500ml")
        self.assertContains(r_offers, "-95% vs média")

        r_cat = self.client.get(reverse("moderation") + "?tab=catalog")
        self.assertContains(r_cat, "Biscoito Oreo 90g")

        r_mkt = self.client.get(reverse("moderation") + "?tab=markets")
        self.assertContains(r_mkt, "Supermercado Central")
        self.assertContains(r_mkt, "Buscar GPS")

        r_ban = self.client.get(reverse("moderation") + "?tab=banned")
        self.assertContains(r_ban, "troll01")

        self.client.post(reverse("moderation_offer_action", kwargs={"offer_id": 77}), {"action": "approve"})
        mock_moderate.assert_called_once_with("fake-jwt-token", 77, "approve")

        self.client.post(reverse("moderation_product_action", kwargs={"product_id": 88}), {"action": "promote"})
        mock_promote.assert_called_once_with("fake-jwt-token", 88)

        self.client.post(
            reverse("moderation_market_geo", kwargs={"market_id": 9}),
            {"city": "Campinas", "latitude": "-22.9056", "longitude": "-47.0608"},
        )
        mock_update_market.assert_called_once()

    @patch("app.services.create_community_offer")
    @patch("app.services.get_activity_logs")
    @patch("app.services.get_groups")
    @patch("app.services.check_services_health")
    def test_maintenance_live_health_and_offer_simulation(
        self, mock_health, mock_groups, mock_logs, mock_create_offer
    ):
        self._login_session()
        mock_health.return_value = [
            {"name": "Core API", "ok": True, "status_code": 200, "latency_ms": 42, "endpoint": "/core-api/health/", "detail": "Operacional"},
            {"name": "Market API", "ok": True, "status_code": 200, "latency_ms": 51, "endpoint": "/market-api/health/", "detail": "Operacional"},
            {"name": "Product API", "ok": True, "status_code": 200, "latency_ms": 38, "endpoint": "/product-api/health/", "detail": "Operacional"},
        ]
        mock_groups.return_value = [{"id": 1, "name": "Staff"}]
        mock_logs.return_value = [{"action": "offer.published", "description": "Café Pilão", "created_at": "2026-11-22T18:00:00Z"}]
        mock_create_offer.return_value = {"id": 501}

        resp = self.client.get(reverse("maintenance"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Simulador ofertas comunitárias")
        self.assertContains(resp, "Disparar Oferta")
        self.assertContains(resp, "Abrir docs")
        self.assertNotContains(resp, "Preset:")

        json_resp = self.client.get(reverse("maintenance_health_json"))
        self.assertEqual(json_resp.status_code, 200)
        self.assertEqual(len(json_resp.json()["health_checks"]), 3)

        sim = self.client.post(
            reverse("maintenance_simulate_offer"),
            {"product_name": "Café Pilão 500g", "market_name": "Atacadão", "price": "12,90", "city": "São Paulo"},
        )
        self.assertRedirects(sim, reverse("maintenance"), fetch_redirect_response=False)
        mock_create_offer.assert_called_once()

    @patch("app.services.create_staff_user")
    @patch("app.services.get_staff_users")
    def test_staff_manage_and_create_route(self, mock_staff_list, mock_create_staff):
        self._login_session(is_staff=True)
        mock_staff_list.return_value = [
            {"id": 2, "username": "Operador", "email": "staff1@example.com", "is_staff": True}
        ]
        mock_create_staff.return_value = {"created": True, "user": {"id": 10, "email": "novo@example.com", "is_staff": True}}

        resp = self.client.get(reverse("staff_manage"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "staff1@example.com")

        post_resp = self.client.post(
            reverse("staff_create"),
            {
                "email": "novo@staff.com",
                "username": "novo_staff",
                "password": "password123",
                "password2": "password123",
            },
        )
        self.assertRedirects(post_resp, reverse("staff_manage"), fetch_redirect_response=False)
        mock_create_staff.assert_called_once()
