from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse as r
from django.views import View


class cadastro_view(View):
    def get(self, request):
        if request.session.get("access_token") and bool(request.session.get("is_staff")):
            return redirect(r("staff_manage"))
        messages.warning(
            request,
            "Cadastro público desativado. Contas Staff são criadas exclusivamente por um operador Staff.",
        )
        return redirect(r("login"))

    def post(self, request):
        return self.get(request)
