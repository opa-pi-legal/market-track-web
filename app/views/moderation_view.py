from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_brl, format_iso_date, get_session_token

DEFAULT_CATEGORIES = [
    "Mercearia",
    "Bebidas",
    "Laticínios",
    "Carnes e Aves",
    "Hortifrúti",
    "Padaria",
    "Limpeza",
    "Higiene",
    "Congelados",
    "Pet",
    "Geral",
]


def _moderation_redirect(tab: str):
    return redirect(f"{r('moderation')}?tab={tab}")


def _resolve_group_label(group_id, groups_by_id: dict[str, str]) -> str:
    gid = str(group_id or "").strip()
    if not gid or gid.lower() == "global":
        return "Global"
    gname = groups_by_id.get(gid)
    return f"{gname} (#{gid})" if gname else f"Grupo #{gid}"


class moderation_view(View):
    template_name = "moderation_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        active_tab = (request.GET.get("tab") or "offers").strip().lower()
        if active_tab not in ("offers", "catalog", "markets", "banned"):
            active_tab = "offers"

        groups = services.get_groups(token, all_groups=True)
        groups_by_id = {
            str(g.get("id")): (g.get("name") or f"Grupo #{g.get('id')}")
            for g in groups
            if g.get("id") is not None
        }

        # 1. Ofertas denunciadas / em quarentena
        flagged_raw = services.get_community_offers(
            token,
            moderation_status="flagged",
            active_only=False,
        )
        if not flagged_raw:
            all_offers = services.get_community_offers(token, active_only=False)
            flagged_raw = [
                o
                for o in all_offers
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

        # 2. Curadoria para Catálogo Global
        catalog_q = (request.GET.get("catalog_q") or "").strip()
        catalog_q_low = catalog_q.lower()
        catalog_filter = (request.GET.get("catalog_filter") or "all").strip().lower()
        if catalog_filter not in ("all", "with_ean", "missing_ean", "global"):
            catalog_filter = "all"

        all_prods = services.get_products(token, all_groups=True)
        categories_set = set(DEFAULT_CATEGORIES)

        pending_all = []
        global_all = []
        for p in all_prods:
            cat = (p.get("category") or "Geral").strip()
            categories_set.add(cat)
            barcode = (p.get("barcode") or "").strip()
            brand = (p.get("brand") or "").strip()
            gid = p.get("group_id")
            item = {
                "id": p.get("id"),
                "name": p.get("name") or "Produto",
                "brand": brand,
                "category": cat,
                "barcode": barcode,
                "has_ean": bool(barcode),
                "group_id": gid,
                "group_label": _resolve_group_label(gid, groups_by_id),
                "is_global": bool(p.get("is_global")),
                "verified_source": p.get("verified_source") or "group",
                "created_at_fmt": format_iso_date(p.get("created_at")),
            }
            if item["is_global"]:
                global_all.append(item)
            else:
                pending_all.append(item)

        pending_total_count = len(pending_all)
        pending_with_ean_count = sum(1 for p in pending_all if p["has_ean"])
        pending_missing_ean_count = pending_total_count - pending_with_ean_count
        global_total_count = len(global_all)

        source_pool = global_all if catalog_filter == "global" else pending_all
        filtered_catalog = []
        for prod in source_pool:
            if catalog_filter == "with_ean" and not prod["has_ean"]:
                continue
            if catalog_filter == "missing_ean" and prod["has_ean"]:
                continue
            if catalog_q_low:
                haystack = " ".join(
                    [
                        str(prod["id"] or ""),
                        prod["name"],
                        prod["brand"],
                        prod["category"],
                        prod["barcode"],
                        prod["group_label"],
                    ]
                ).lower()
                if catalog_q_low not in haystack:
                    continue
            filtered_catalog.append(prod)

        # Ordena priorizando produtos que já têm EAN para curadoria rápida
        filtered_catalog.sort(key=lambda x: (not x["has_ean"], x["name"].lower()))

        # 3. Manutenção & Saneamento de Mercados
        market_q = (request.GET.get("market_q") or "").strip()
        market_q_low = market_q.lower()
        market_filter = (request.GET.get("market_filter") or "all").strip().lower()
        if market_filter not in ("all", "missing_geo", "with_geo"):
            market_filter = "all"

        all_markets = services.get_markets(token, all_groups=True)
        markets_all_mapped = []
        for m in all_markets:
            lat = m.get("latitude")
            lng = m.get("longitude")
            missing_geo = lat is None or lng is None
            gid = m.get("group_id")
            markets_all_mapped.append(
                {
                    "id": m.get("id"),
                    "name": m.get("name") or "Mercado",
                    "brand": m.get("brand") or "",
                    "address": m.get("address") or "",
                    "city": m.get("city") or "",
                    "latitude": "" if lat is None else lat,
                    "longitude": "" if lng is None else lng,
                    "group_id": gid,
                    "group_label": _resolve_group_label(gid, groups_by_id),
                    "is_verified": bool(m.get("is_verified")),
                    "linked_groups_count": int(m.get("linked_groups_count") or 1),
                    "created_at_fmt": format_iso_date(m.get("created_at")),
                    "missing_geo": missing_geo,
                }
            )

        markets_all_mapped.sort(key=lambda m: (not m["missing_geo"], m["name"].lower()))
        total_markets_count = len(markets_all_mapped)
        missing_geo_count = sum(1 for m in markets_all_mapped if m["missing_geo"])
        with_geo_count = total_markets_count - missing_geo_count

        markets = []
        for m in markets_all_mapped:
            if market_filter == "missing_geo" and not m["missing_geo"]:
                continue
            if market_filter == "with_geo" and m["missing_geo"]:
                continue
            if market_q_low:
                haystack = " ".join(
                    [
                        str(m["id"] or ""),
                        m["name"],
                        m["brand"],
                        m["city"],
                        m["address"],
                        m["group_label"],
                    ]
                ).lower()
                if market_q_low not in haystack:
                    continue
            markets.append(m)

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
                "pending_global_products": filtered_catalog[:100],
                "pending_total_count": pending_total_count,
                "pending_with_ean_count": pending_with_ean_count,
                "pending_missing_ean_count": pending_missing_ean_count,
                "global_total_count": global_total_count,
                "catalog_q": catalog_q,
                "catalog_filter": catalog_filter,
                "catalog_categories": sorted(categories_set),
                "markets": markets[:120],
                "total_markets_count": total_markets_count,
                "missing_geo_count": missing_geo_count,
                "with_geo_count": with_geo_count,
                "market_q": market_q,
                "market_filter": market_filter,
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
        update_fields = {}
        for field in ("name", "brand", "category", "barcode"):
            if field in request.POST:
                val = (request.POST.get(field) or "").strip()
                if field == "name" and val:
                    update_fields["name"] = val
                elif field == "category" and val:
                    update_fields["category"] = val
                elif field in ("brand", "barcode"):
                    update_fields[field] = val or None

        try:
            if action == "save":
                if update_fields:
                    services.update_product(token, product_id, update_fields)
                    messages.success(request, f"Dados do produto #{product_id} atualizados na curadoria.")
            elif action == "promote":
                if update_fields:
                    services.update_product(token, product_id, update_fields)
                services.promote_product_global(token, product_id)
                messages.success(request, f"Produto #{product_id} revisado e promovido ao Catálogo Global!")
            elif action == "reject":
                services.delete_product(token, product_id)
                messages.info(request, f"Produto #{product_id} recusado e removido.")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return _moderation_redirect("catalog")


class moderation_product_bulk_promote_view(View):
    def post(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        mode = (request.POST.get("mode") or "with_ean").strip().lower()
        all_prods = services.get_products(token, all_groups=True)
        candidates = [
            p
            for p in all_prods
            if not p.get("is_global")
            and (mode == "all" or bool((p.get("barcode") or "").strip()))
        ]

        if not candidates:
            messages.warning(request, "Nenhum produto elegível encontrado para promoção em lote.")
            return _moderation_redirect("catalog")

        promoted = 0
        for p in candidates:
            pid = p.get("id")
            if not pid:
                continue
            try:
                services.promote_product_global(token, pid)
                promoted += 1
            except services.APIError:
                pass

        messages.success(
            request,
            f"{promoted} produto(s) promovido(s) ao Catálogo Global com sucesso!",
        )
        return _moderation_redirect("catalog")


class moderation_market_create_view(View):
    def post(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Informe o nome do mercado.")
            return _moderation_redirect("markets")

        brand = (request.POST.get("brand") or "").strip()
        city = (request.POST.get("city") or "").strip()
        address = (request.POST.get("address") or "").strip()
        lat_raw = (request.POST.get("latitude") or "").strip().replace(",", ".")
        lng_raw = (request.POST.get("longitude") or "").strip().replace(",", ".")

        payload: dict = {
            "group_id": "global",
            "name": name,
            "brand": brand,
            "city": city,
            "address": address,
            "status": "active",
        }
        try:
            if lat_raw:
                payload["latitude"] = float(lat_raw)
            if lng_raw:
                payload["longitude"] = float(lng_raw)
        except ValueError:
            messages.error(request, "Coordenadas inválidas. Use formato decimal (ex.: -23.5505).")
            return _moderation_redirect("markets")

        try:
            services.create_market(token, payload)
            request.session.pop("_nav_badge_ts", None)
            messages.success(request, f"Mercado '{name}' criado com sucesso!")
        except services.APIError as exc:
            messages.error(request, f"Não foi possível criar o mercado: {exc}")
        return _moderation_redirect("markets")


class moderation_market_geo_view(View):
    def post(self, request, market_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        payload = {}
        if "name" in request.POST:
            name_val = (request.POST.get("name") or "").strip()
            if name_val:
                payload["name"] = name_val
        if "brand" in request.POST:
            payload["brand"] = (request.POST.get("brand") or "").strip()
        if "address" in request.POST:
            payload["address"] = (request.POST.get("address") or "").strip()
        if "city" in request.POST:
            city_val = (request.POST.get("city") or "").strip()
            if city_val or "name" in request.POST:
                payload["city"] = city_val

        lat_raw = (request.POST.get("latitude") or "").strip().replace(",", ".")
        lng_raw = (request.POST.get("longitude") or "").strip().replace(",", ".")

        try:
            if lat_raw:
                payload["latitude"] = float(lat_raw)
            if lng_raw:
                payload["longitude"] = float(lng_raw)
        except ValueError:
            messages.error(request, "Coordenadas inválidas. Use formato decimal (ex.: -23.5505).")
            return _moderation_redirect("markets")

        if not payload:
            messages.warning(request, "Preencha os dados ou coordenadas do mercado para atualizar.")
            return _moderation_redirect("markets")

        try:
            services.update_market(token, market_id, payload)
            request.session.pop("_nav_badge_ts", None)
            messages.success(request, f"Mercado #{market_id} atualizado com sucesso!")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return _moderation_redirect("markets")


class moderation_market_verify_view(View):
    def post(self, request, market_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        try:
            services.verify_market(token, market_id)
            messages.success(request, f"Mercado #{market_id} marcado como Verificado na comunidade!")
        except services.APIError as exc:
            messages.error(request, f"Não foi possível verificar o mercado: {exc}")
        return _moderation_redirect("markets")


class moderation_market_delete_view(View):
    def post(self, request, market_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        try:
            services.delete_market(token, market_id)
            request.session.pop("_nav_badge_ts", None)
            messages.success(request, f"Mercado #{market_id} excluído com sucesso.")
        except services.APIError as exc:
            messages.error(request, f"Não foi possível excluir o mercado: {exc}")
        return _moderation_redirect("markets")
