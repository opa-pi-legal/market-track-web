from datetime import datetime

from django.conf import settings

from app import services


def is_email_allowed(email: str | None) -> bool:
    allowed = getattr(settings, "ALLOWED_WEB_EMAILS", set())
    if not allowed:
        return True
    normalized = (email or "").strip().lower()
    return bool(normalized and normalized in allowed)


def get_firebase_web_config() -> dict:
    return {
        "apiKey": getattr(settings, "FIREBASE_API_KEY", ""),
        "authDomain": getattr(settings, "FIREBASE_AUTH_DOMAIN", ""),
        "projectId": getattr(settings, "FIREBASE_PROJECT_ID", ""),
    }


def get_session_token(request) -> str | None:
    token = request.session.get("access_token")
    if not (isinstance(token, str) and token.strip()):
        return None

    if "is_staff" in request.session and not bool(request.session.get("is_staff")):
        request.session.flush()
        return None

    session_email = (request.session.get("user_email") or "").strip().lower()
    if "is_staff" not in request.session or not session_email:
        me = services.get_current_user(token)
        if not me or not bool(me.get("is_staff")):
            request.session.flush()
            return None
        request.session["user_name"] = me.get("username") or ""
        request.session["user_email"] = (me.get("email") or "").strip().lower()
        request.session["is_staff"] = True
        request.session["active_group_id"] = me.get("last_active_group")

    return token


def format_brl(cents) -> str:
    try:
        val = int(round(float(cents or 0)))
    except (TypeError, ValueError):
        val = 0
    return f"R$ {val / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_iso_date(raw: str | None, with_time: bool = False) -> str:
    if not raw:
        return "-"
    try:
        cleaned = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y")
    except ValueError:
        return str(raw)[:10]


def parse_price_to_cents(raw: str) -> int:
    cleaned = (raw or "").strip().replace("R$", "").replace(" ", "")
    if not cleaned:
        return 0
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        val = float(cleaned)
        return max(0, int(round(val * 100)))
    except ValueError:
        return 0
