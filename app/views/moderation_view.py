from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_brl, format_iso_date, get_session_token


def _moderation_redirect(tab: str):
    return redirect(f"{r('moderation')}?tab={tab}")


class moderation_view(View):
    template_name = "moderation_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        active_tab = (request.GET.get("tab") or "offers").strip().lower()
        if active_tab not in ("offers", "catalog", "markets", "banned"):
            active_tab = "offers"

        # 1. Ofertas denunciadas / em quarentena
        flagged_raw = services.get_community_offers(
            token,
            moderation_status="flagged",
            active_only=False,
        )
        if not flagged_raw:
            all_offers = services.get_community_offers(token, active_only=False)
            flagged_raw = [
                o for o in all_offers
                if o.get("moderation_status") in ("flagged", "removed")
                or int(o.get("abuse_reports_count") or 0) > 0
                or int(o.get("reports_count") or 0) > 0
            ]

        flagged_offers = []
        for o in flagged_raw:
            ref_cents = int(o.get("reference_avg_cents") or 0)
            cur_cents = int(o.get("price_cents") or 0)
            deviation_label = ""
            if ref_cents > 0 and cur_cents > 0:
                diff_pct = int(round(((cur_cents - ref_cents) / ref_cents) * 100))
                if diff_pct != 0:
                    sign = "+" if diff_pct > 0 else ""
                    deviation_label = f"{sign}{diff_pct}% vs média"

            flagged_offers.append(
                {
                    "id": o.get("id"),
                    "product_name": o.get("product_name") or "Oferta",
                    "market_name": o.get("market_name") or "",
                    "original_price_fmt": format_brl(ref_cents) if ref_cents else "—",
                    "current_price_fmt": format_brl(cur_cents),
                    "deviation_label": deviation_label,
                    "abuse_reports_count": int(o.get("abuse_reports_count") or 0),
                    "reports_count": int(o.get("reports_count") or 0),
                    "reported_by_name": o.get("reported_by_name") or "Comunidade",
                    "moderation_status": o.get("moderation_status") or "flagged",
                }
            )

        # 2. Produtos aguardando curadoria para Catálogo Global
        all_prods = services.get_products(token, all_groups=True)
        pending_global_products = [
            {
                "id": p.get("id"),
                "name": p.get("name") or "Produto",
                "category": p.get("category") or "Geral",
                "barcode": (p.get("barcode") or "").strip(),
                "group_id": p.get("group_id"),
            }
            for p in all_prods
            if not p.get("is_global")
        ][:40]

        # 3. Saneamento de Mercados
        all_markets = services.get_markets(token, all_groups=True)
        markets = [
            {
                "id": m.get("id"),
                "name": m.get("name") or "Mercado",
                "city": m.get("city") or "",
                "latitude": "" if m.get("latitude") is None else m.get("latitude"),
                "longitude": "" if m.get("longitude") is None else m.get("longitude"),
                "created_at_fmt": format_iso_date(m.get("created_at")),
                "missing_geo": m.get("latitude") is None or m.get("longitude") is None,
            }
            for m in all_markets
        ]
        markets.sort(key=lambda m: (not m["missing_geo"], m["name"].lower()))
        missing_geo_count = sum(1 for m in markets if m["missing_geo"])

        # 4. Contas restritas
        users = services.get_users(token)
        banned_users = [u for u in users if u.get("community_banned") is True]

        # Atualiza badge da navbar
        request.session["_nav_mod_count"] = len(flagged_offers) + missing_geo_count

        return render(
            request,
            self.template_name,
            {
                "active_nav": "moderation",
                "active_tab": active_tab,
                "flagged_offers": flagged_offers,
                "pending_global_products": pending_global_products,
                "markets": markets[:40],
                "missing_geo_count": missing_geo_count,
                "banned_users": banned_users,
                "is_staff": True,
            },
        )


class moderation_offer_action_view(View):
    def post(self, request, offer_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        action = (request.POST.get("action") or "").strip().lower()
        labels = {
            "approve": "Oferta restaurada no feed com sucesso.",
            "remove": "Oferta removida definitivamente.",
            "ban_author": "Oferta removida e autor bloqueado da comunidade global.",
        }
        try:
            services.moderate_offer(token, offer_id, action)
            request.session.pop("_nav_badge_ts", None)
            messages.success(request, labels.get(action, "Ação de moderação aplicada."))
        except services.APIError as exc:
            messages.error(request, str(exc))
        return _moderation_redirect("offers")


class moderation_product_action_view(View):
    def post(self, request, product_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        action = (request.POST.get("action") or "promote").strip().lower()
        try:
            if action == "promote":
                services.promote_product_global(token, product_id)
                messages.success(request, f"Produto #{product_id} promovido ao Catálogo Global!")
            elif action == "reject":
                services.delete_product(token, product_id)
                messages.info(request, f"Produto #{product_id} recusado e removido.")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return _moderation_redirect("catalog")


class moderation_market_geo_view(View):
    def post(self, request, market_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        city = (request.POST.get("city") or "").strip()
        lat_raw = (request.POST.get("latitude") or "").strip().replace(",", ".")
        lng_raw = (request.POST.get("longitude") or "").strip().replace(",", ".")

        payload = {}
        if city:
            payload["city"] = city
        try:
            if lat_raw:
                payload["latitude"] = float(lat_raw)
            if lng_raw:
                payload["longitude"] = float(lng_raw)
        except ValueError:
            messages.error(request, "Coordenadas inválidas. Use formato decimal (ex.: -23.5505).")
            return _moderation_redirect("markets")

        if not payload:
            messages.warning(request, "Preencha cidade, latitude ou longitude para atualizar.")
            return _moderation_redirect("markets")

        try:
            services.update_market(token, market_id, payload)
            request.session.pop("_nav_badge_ts", None)
            messages.success(request, f"Localização do mercado #{market_id} atualizada!")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return _moderation_redirect("markets")
