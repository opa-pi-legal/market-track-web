from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app.services import APIError, get_current_user, login_with_api
from app.views.helpers import get_firebase_web_config


class login_view(View):
    template_name = "login_template.html"

    def get(self, request):
        if request.session.get("access_token") and bool(request.session.get("is_staff")):
            return redirect(r("dashboard"))

        return render(request, self.template_name, self._empty_context())

    def post(self, request):
        context = self._empty_context()

        identifier = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        context["form"]["email"]["value"] = identifier

        if not identifier:
            context["form"]["email"]["errors"].append("Informe seu email ou usuário.")
        if not password:
            context["form"]["password"]["errors"].append("Informe sua senha.")

        if not context["form"]["email"]["errors"] and not context["form"]["password"]["errors"]:
            try:
                tokens = login_with_api(username=identifier, password=password)
                access = tokens.get("access")
                user_data = tokens.get("user") if isinstance(tokens.get("user"), dict) else None
                if not user_data and access:
                    user_data = get_current_user(access) or {}

                if not bool((user_data or {}).get("is_staff")):
                    context["form"]["non_field_errors"].append(
                        "Acesso restrito: apenas contas com permissão de Staff podem acessar o painel web."
                    )
                    return render(request, self.template_name, context)

                resolved_email = (
                    (user_data or {}).get("email")
                    or (identifier if "@" in identifier else "")
                ).strip().lower()

                request.session["access_token"] = access
                request.session["refresh_token"] = tokens.get("refresh")
                request.session["user_email"] = resolved_email
                request.session["user_name"] = (user_data or {}).get("username") or identifier
                request.session["is_staff"] = True
                request.session["active_group_id"] = (user_data or {}).get("last_active_group")

                return redirect(r("dashboard"))
            except APIError as exc:
                context["form"]["non_field_errors"].append(str(exc))

        return render(request, self.template_name, context)

    @staticmethod
    def _empty_context():
        return {
            "form": {
                "email": {"value": "", "errors": []},
                "password": {"errors": []},
                "non_field_errors": [],
            },
            "firebase_config": get_firebase_web_config(),
        }
