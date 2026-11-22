from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View
from app.services import APIError, register_with_api

class cadastro_view(View):
    template_name = "cadastro_template.html"

    def get(self, request):
        if request.session.get("access_token"):
            return redirect(r("dashboard"))

        return render(request, self.template_name, self._empty_context())

    def post(self, request):
        context = self._empty_context()

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        photo_url = request.POST.get("photo", "").strip()
        

        if not username and "@" in email:
            username = email.split("@", 1)[0]

        context["form"]["email"]["value"] = email

        if not email:
            context["form"]["email"]["errors"].append("Informe seu email.")
        if not password:
            context["form"]["password"]["errors"].append("Informe sua senha.")
        if not password2:
            context["form"]["password2"]["errors"].append("Confirme sua senha.")
        elif password != password2:
            context["form"]["password2"]["errors"].append("As senhas não coincidem.")

        has_errors = (
            bool(context["form"]["email"]["errors"])
            or bool(context["form"]["password"]["errors"])
            or bool(context["form"]["password2"]["errors"])
            or bool(context["form"]["photo"]["errors"])
        )

        if not has_errors:
            try:
                register_with_api(
                    username=username,
                    email=email,
                    photo_url=photo_url,
                    password=password,
                    password2=password2,
                )
                return redirect(r("login"))
            except APIError as exc:
                context["form"]["non_field_errors"].append(str(exc))

        return render(request, self.template_name, context)

    @staticmethod
    def _empty_context():
        return {
            "form": {
                "email": {"value": "", "errors": []},
                "password": {"errors": []},
                "password2": {"errors": []},
                "photo": {"errors": []},
                "non_field_errors": [],
            }
        }