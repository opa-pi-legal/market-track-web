import json

from django.http import JsonResponse
from django.urls import reverse as r
from django.views import View

from app.services import (
    APIError,
    get_current_user,
    google_login_with_api,
    verify_firebase_id_token,
)
from app.views.helpers import is_email_allowed


class google_login_view(View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"error": "Requisição inválida."}, status=400)

        id_token = (body.get("id_token") or "").strip()
        if not id_token:
            return JsonResponse({"error": "Token Google não recebido."}, status=400)

        try:
            google_user = verify_firebase_id_token(id_token)
        except APIError as exc:
            return JsonResponse({"error": str(exc)}, status=401)

        email = google_user["email"]

        try:
            tokens = google_login_with_api(
                email=email,
                username=google_user.get("display_name") or email.split("@")[0],
                photo_url=google_user.get("photo_url"),
                staff_only=True,
            )
        except APIError as exc:
            code = exc.status_code if exc.status_code in (400, 401, 403) else 502
            return JsonResponse({"error": str(exc)}, status=code)

        access = tokens.get("access")
        if not access:
            return JsonResponse({"error": "API não retornou token de acesso."}, status=502)

        user_data = tokens.get("user") if isinstance(tokens.get("user"), dict) else None
        if not user_data:
            user_data = get_current_user(access) or {}

        resolved_email = (user_data.get("email") or email).strip().lower()
        is_staff = bool(user_data.get("is_staff"))

        if not is_staff:
            return JsonResponse(
                {
                    "error": (
                        "Acesso restrito: apenas contas com permissão de Staff "
                        "podem acessar o painel web."
                    )
                },
                status=403,
            )

        # Mantém compatibilidade: se o e-mail estiver na whitelist ou já for Staff no banco, entra!
        if not is_staff and not is_email_allowed(resolved_email):
            return JsonResponse(
                {"error": "Acesso restrito: conta não autorizada."},
                status=403,
            )

        request.session["access_token"] = access
        request.session["refresh_token"] = tokens.get("refresh")
        request.session["user_email"] = resolved_email
        request.session["user_name"] = user_data.get("username") or google_user.get("display_name") or resolved_email
        request.session["is_staff"] = True
        request.session["active_group_id"] = user_data.get("last_active_group")

        return JsonResponse({"redirect_url": r("dashboard")}, status=200)
