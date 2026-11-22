from django.shortcuts import redirect
from django.urls import reverse as r
from django.views import View


class logout_view(View):
    def post(self, request):
        request.session.flush()
        return redirect(r("login"))

    def get(self, request):
        request.session.flush()
        return redirect(r("login"))
