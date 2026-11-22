from django.views import View
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse as r
from app.services import login_with_api, APIError
class login_view(View):
    template_name = "login_template.html"

    def get(self, request):
        if request.session.get("access_token"):
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

                request.session["access_token"] = tokens.get("access")
                request.session["refresh_token"] = tokens.get("refresh")

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
            }
        }