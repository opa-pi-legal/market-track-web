from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_brl, format_iso_date, get_session_token


class lists_view(View):
    template_name = "lists_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        raw_q = (request.GET.get("q") or "").strip()
        q = raw_q.lower()
        q_id = q.lstrip("#").strip()

        raw_lists = services.get_shopping_lists(token, all_groups=True, query=raw_q)

        # Fallback de nomes de grupos/usuários caso algum registro venha sem campos enriquecidos
        needs_group_lookup = any(not sl.get("group_name") and sl.get("group") for sl in raw_lists)
        groups_by_id = (
            {str(g.get("id")): g.get("name", "Grupo") for g in services.get_groups(token, all_groups=True)}
            if needs_group_lookup
            else {}
        )

        needs_user_lookup = any(
            not sl.get("owner_username") and not sl.get("owner_email") and sl.get("owner")
            for sl in raw_lists
        )
        users_by_id = (
            {str(u.get("id")): u for u in services.get_users(token)}
            if needs_user_lookup
            else {}
        )

        shopping_lists = []
        seen_ids = set()
        for sl in raw_lists:
            lid = sl.get("id")
            if lid in seen_ids:
                continue
            seen_ids.add(lid)

            name = sl.get("name") or "Lista sem nome"
            gname = (
                sl.get("group_name")
                or groups_by_id.get(str(sl.get("group") or ""), "")
                or "Sem grupo"
            )
            owner_obj = users_by_id.get(str(sl.get("owner") or ""), {})
            owner_name = (
                sl.get("owner_username")
                or owner_obj.get("username")
                or ""
            )
            owner_email = (
                sl.get("owner_email")
                or owner_obj.get("email")
                or ""
            )

            # Filtro local complementar (garante busca por ID com/sem #, lista, usuário, e-mail, membros e grupo)
            if q:
                lid_str = str(lid or "").lower()
                member_names = [str(m).lower() for m in (sl.get("member_names") or [])]
                matches_id = bool(q_id) and lid_str == q_id
                matches_text = (
                    q in name.lower()
                    or q in gname.lower()
                    or q in owner_name.lower()
                    or q in owner_email.lower()
                    or q in lid_str
                    or any(q in m for m in member_names)
                )
                if not (matches_id or matches_text):
                    continue

            items_count = sl.get("items_count")
            shopping_lists.append(
                {
                    "id": lid,
                    "name": name,
                    "owner_name": owner_name or owner_email or "Não informado",
                    "owner_email": owner_email if owner_name else "",
                    "group_name": gname,
                    "items_count": int(items_count) if items_count is not None else None,
                    "status": sl.get("status", "active"),
                    "budget_fmt": format_brl(sl.get("budget_cents")) if sl.get("budget_cents") else "Sem teto",
                    "created_at_fmt": format_iso_date(sl.get("created_at")),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "active_nav": "lists",
                "shopping_lists": shopping_lists,
                "q": raw_q,
            },
        )


class list_detail_view(View):
    template_name = "list_detail_template.html"

    def get(self, request, list_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        sl = services.get_shopping_list(token, list_id, all_groups=True)
        if not sl:
            messages.error(request, "Lista de compras não encontrada.")
            return redirect(r("lists"))

        group_id = sl.get("group")
        members_raw = (
            services.get_group_members(token, group_id, all_groups=True) if group_id else []
        )
        items_raw = services.get_shopping_list_items(token, list_id, all_groups=True)

        participants = [
            {
                "membership_id": m.get("id"),
                "name": m.get("user_username") or m.get("user_email") or f"Usuário #{m.get('user')}",
                "email": m.get("user_email") or "",
                "is_admin": bool(m.get("is_admin")),
            }
            for m in members_raw
        ]

        total_spent_cents = 0
        total_estimated_cents = 0
        items = []
        for it in items_raw:
            qty_raw = it.get("quantity", 1)
            try:
                qty_num = float(qty_raw)
                qty_label = str(int(qty_num)) if qty_num.is_integer() else f"{qty_num:.2f}".replace(".", ",")
            except (TypeError, ValueError):
                qty_num = 1.0
                qty_label = "1"

            sel_cents = int(it.get("selected_price_cents") or 0)
            paid_cents = int(it.get("paid_price_cents") or 0)
            unit_cents = paid_cents or sel_cents
            total_estimated_cents += int(round(sel_cents * qty_num))
            total_spent_cents += int(round(unit_cents * qty_num))

            items.append(
                {
                    "id": it.get("id"),
                    "qty_label": qty_label,
                    "product_name": it.get("product_name") or "Produto",
                    "price_fmt": format_brl(unit_cents) if unit_cents > 0 else "Sem preço",
                    "checked": bool(it.get("checked")),
                }
            )

        budget_cents = int(sl.get("budget_cents") or 0)
        if budget_cents > 0 and total_spent_cents > 0:
            economy_cents = max(0, budget_cents - total_spent_cents)
        elif total_estimated_cents > total_spent_cents:
            economy_cents = total_estimated_cents - total_spent_cents
        else:
            economy_cents = 0

        budget_pct = (
            min(100, int(round((total_spent_cents / budget_cents) * 100)))
            if budget_cents > 0
            else 0
        )
        budget_over = budget_cents > 0 and total_spent_cents > budget_cents

        owner_name = sl.get("owner_username") or sl.get("owner_email") or "Não informado"
        owner_email = sl.get("owner_email") or ""
        group_name = sl.get("group_name") or (f"Grupo #{group_id}" if group_id else "Sem grupo")

        return render(
            request,
            self.template_name,
            {
                "active_nav": "lists",
                "shopping_list": sl,
                "owner_name": owner_name,
                "owner_email": owner_email,
                "group_name": group_name,
                "participants": participants,
                "items": items,
                "budget_fmt": format_brl(budget_cents) if budget_cents > 0 else "Não definido",
                "spent_fmt": format_brl(total_spent_cents),
                "economy_fmt": format_brl(economy_cents),
                "budget_pct": budget_pct,
                "budget_over": budget_over,
                "has_budget": budget_cents > 0,
            },
        )


class list_delete_view(View):
    def post(self, request, list_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))
        try:
            services.delete_shopping_list(token, list_id)
            messages.success(request, "Lista apagada com sucesso.")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return redirect(r("lists"))


class list_item_delete_view(View):
    def post(self, request, list_id, item_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))
        try:
            services.delete_shopping_list_item(token, item_id)
            messages.success(request, "Item removido da lista.")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return redirect(r("list_detail", kwargs={"list_id": list_id}))


class list_member_delete_view(View):
    def post(self, request, list_id, membership_id):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))
        try:
            services.remove_group_member(token, membership_id)
            messages.success(request, "Participante removido do grupo.")
        except services.APIError as exc:
            messages.error(request, str(exc))
        return redirect(r("list_detail", kwargs={"list_id": list_id}))
