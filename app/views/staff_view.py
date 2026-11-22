from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_iso_date, get_session_token


class staff_manage_view(View):
    template_name = "staff_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token or not bool(request.session.get("is_staff")):
            return redirect(r("login"))

        staff_raw = services.get_staff_users(token)
        if not staff_raw:
            all_users = services.get_users(token)
            staff_raw = [u for u in all_users if u.get("is_staff") is True]

        staff_users = [
            {
                "id": u.get("id"),
                "username": u.get("username") or "-",
                "email": u.get("email") or "-",
                "is_superuser": bool(u.get("is_superuser")),
                "created_at_fmt": format_iso_date(u.get("created_at") or u.get("date_joined")),
            }
            for u in staff_raw
        ]

        return render(
            request,
            self.template_name,
            {
                "active_nav": "staff",
                "staff_users": staff_users,
            },
        )


class staff_create_view(View):
    def post(self, request):
        token = get_session_token(request)
        if not token or not bool(request.session.get("is_staff")):
            return redirect(r("login"))

        email = (request.POST.get("email") or "").strip().lower()
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""

        if not email or "@" not in email:
            messages.error(request, "Informe um e-mail válido para a conta Staff.")
            return redirect(r("staff_manage"))

        if password and password != password2:
            messages.error(request, "As senhas informadas não coincidem.")
            return redirect(r("staff_manage"))

        try:
            result = services.create_staff_user(
                token,
                email=email,
                username=username,
                password=password,
            )
            if isinstance(result, dict) and result.get("created") is False:
                messages.success(
                    request,
                    f"Conta existente ({email}) promovida para Staff com sucesso!",
                )
            else:
                messages.success(
                    request,
                    f"Nova conta Staff ({email}) criada com sucesso!",
                )
        except services.APIError as exc:
            messages.error(request, str(exc))

        return redirect(r("staff_manage"))
