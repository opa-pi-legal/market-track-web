from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

class dashboard_view(View):
    template_name = "dashboard_template.html"

    def get(self, request):
        if request.session.get("access_token"):
            return render(request, self.template_name)

        return render(request, self.template_name, self._empty_context())

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