import json

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_brl, format_iso_date, get_session_token


def _resolve_products_for_session(request, token: str, query: str = "") -> list[dict]:
    is_staff = bool(request.session.get("is_staff"))
    if is_staff:
        prods = services.get_products(token, all_groups=True, query=query)
        if prods:
            return prods

    active_gid = request.session.get("active_group_id")
    if not active_gid:
        groups = services.get_groups(token)
        if groups:
            active_gid = groups[0].get("id")
            request.session["active_group_id"] = active_gid

    return services.get_products(token, group_id=active_gid, include_global=True, query=query)


class products_view(View):
    template_name = "products_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        q = (request.GET.get("q") or "").strip()
        origin = (request.GET.get("origin") or "all").strip().lower()
        selected_category = (request.GET.get("category") or "").strip()

        raw_products = _resolve_products_for_session(request, token, query=q)
        offers = services.get_community_offers(token, active_only=True)

        price_by_ean: dict[str, int] = {}
        price_by_name: dict[str, int] = {}
        for off in offers:
            cents = int(off.get("price_cents") or 0)
            if cents <= 0:
                continue
            ean = (off.get("ean") or "").strip()
            pname = (off.get("product_name") or "").strip().lower()
            if ean and (ean not in price_by_ean or cents < price_by_ean[ean]):
                price_by_ean[ean] = cents
            if pname and (pname not in price_by_name or cents < price_by_name[pname]):
                price_by_name[pname] = cents

        categories_set: set[str] = set()
        products = []
        for p in raw_products:
            cat = (p.get("category") or "Geral").strip()
            categories_set.add(cat)

            is_global = bool(p.get("is_global"))
            if origin == "global" and not is_global:
                continue
            if origin == "group" and is_global:
                continue
            if selected_category and cat.lower() != selected_category.lower():
                continue

            ean = (p.get("barcode") or "").strip()
            name = p.get("name") or "Produto"
            cents = price_by_ean.get(ean) or price_by_name.get(name.strip().lower())
            products.append(
                {
                    "id": p.get("id"),
                    "name": name,
                    "brand": p.get("brand") or "",
                    "category": cat,
                    "barcode": ean,
                    "status": p.get("status") or "active",
                    "is_global": is_global,
                    "price_fmt": format_brl(cents) if cents else "Sem cotação",
                    "has_price": bool(cents),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "active_nav": "products",
                "products": products,
                "categories": sorted(categories_set),
                "selected_category": selected_category,
                "q": q,
                "origin": origin,
            },
        )


class product_create_view(View):
    def post(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Informe o nome do produto.")
            return redirect(r("products"))

        payload = {
            "name": name,
            "brand": (request.POST.get("brand") or "").strip() or None,
            "category": (request.POST.get("category") or "Geral").strip(),
            "barcode": (request.POST.get("barcode") or "").strip() or None,
            "status": "active",
            "is_global": True,
            "verified_source": "admin",
        }
        photo_url = (request.POST.get("photo_url") or "").strip()
        if photo_url:
            payload["photo_url"] = photo_url

        try:
            created = services.create_product(token, payload)
            pid = created.get("id") if isinstance(created, dict) else None
            if pid and not created.get("is_global"):
                try:
                    services.promote_product_global(token, pid)
                except services.APIError:
                    pass
            messages.success(request, f"Produto '{name}' adicionado ao Catálogo Global!")
        except services.APIError as exc:
            messages.error(request, f"Não foi possível criar o produto: {exc}")

        return redirect(r("products"))


class product_detail_view(View):
    template_name = "product_detail_template.html"

    def get(self, request, product_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        product = services.get_product(token, product_id)
        if not product:
            messages.error(request, "Produto não encontrado.")
            return redirect(r("products"))

        ean = (product.get("barcode") or "").strip()
        pname = (product.get("name") or "").strip().lower()
        offers = services.get_community_offers(token, active_only=False)

        price_history = []
        for off in offers:
            off_ean = (off.get("ean") or "").strip()
            off_name = (off.get("product_name") or "").strip().lower()
            if (ean and off_ean == ean) or (pname and (pname in off_name or off_name in pname)):
                cents = int(off.get("price_cents") or 0)
                price_history.append(
                    {
                        "market_name": off.get("market_name") or "Mercado",
                        "price_cents": cents,
                        "price_brl": round(cents / 100, 2),
                        "price_fmt": format_brl(cents),
                        "date_fmt": format_iso_date(off.get("created_at"), with_time=True),
                        "date_short": format_iso_date(off.get("created_at"), with_time=False),
                        "discount_percent": int(off.get("discount_percent") or 0),
                    }
                )

        latest_price_fmt = price_history[0]["price_fmt"] if price_history else "Sem cotação"
        status_label = "Ativo" if (product.get("status") or "active") == "active" else "Arquivado"

        chart_points = list(reversed(price_history[:12]))
        price_chart = {
            "labels": [f"{p['date_short']} · {p['market_name'][:14]}" for p in chart_points],
            "values": [p["price_brl"] for p in chart_points],
        }

        return render(
            request,
            self.template_name,
            {
                "active_nav": "products",
                "product": product,
                "status_label": status_label,
                "created_at_fmt": format_iso_date(product.get("created_at")),
                "updated_at_fmt": format_iso_date(product.get("last_updated")),
                "latest_price_fmt": latest_price_fmt,
                "price_history": price_history[:15],
                "price_chart_json": json.dumps(price_chart),
            },
        )


class product_edit_view(View):
    def post(self, request, product_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        payload = {
            "name": (request.POST.get("name") or "").strip(),
            "brand": (request.POST.get("brand") or "").strip() or None,
            "category": (request.POST.get("category") or "Geral").strip(),
            "barcode": (request.POST.get("barcode") or "").strip() or None,
            "status": (request.POST.get("status") or "active").strip(),
        }
        photo_url = (request.POST.get("photo_url") or "").strip()
        if photo_url:
            payload["photo_url"] = photo_url

        try:
            services.update_product(token, product_id, payload)
            messages.success(request, "Produto atualizado com sucesso.")
        except services.APIError as exc:
            messages.error(request, str(exc))

        return redirect(r("product_detail", kwargs={"product_id": product_id}))


class product_promote_view(View):
    def post(self, request, product_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        try:
            services.promote_product_global(token, product_id)
            messages.success(request, "Produto promovido ao Catálogo Global!")
        except services.APIError as exc:
            messages.error(request, str(exc))

        return redirect(r("product_detail", kwargs={"product_id": product_id}))


class product_delete_view(View):
    def post(self, request, product_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        try:
            services.delete_product(token, product_id)
            messages.success(request, "Produto apagado com sucesso.")
        except services.APIError as exc:
            messages.error(request, str(exc))

        return redirect(r("products"))
