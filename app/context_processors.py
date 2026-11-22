import time

from app import services


def _initials(name: str, email: str) -> str:
    source = (name or email or "MT").strip()
    parts = [p for p in source.replace("@", " ").replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return source[:2].upper()


def app_chrome(request):
    token = request.session.get("access_token")
    if not token or not bool(request.session.get("is_staff")):
        return {}

    name = (request.session.get("user_name") or "").strip()
    email = (request.session.get("user_email") or "").strip()

    now = int(time.time())
    cached_ts = int(request.session.get("_nav_badge_ts") or 0)
    mod_count = request.session.get("_nav_mod_count")

    if mod_count is None or (now - cached_ts) > 30:
        try:
            flagged = services.get_community_offers(token, moderation_status="flagged", active_only=False)
            markets = services.get_markets(token, all_groups=True)
            missing_geo = sum(1 for m in markets if m.get("latitude") is None or m.get("longitude") is None)
            mod_count = len(flagged) + missing_geo
        except Exception:
            mod_count = 0
        request.session["_nav_mod_count"] = mod_count
        request.session["_nav_badge_ts"] = now

    return {
        "nav_user": {
            "name": name or (email.split("@")[0] if email else "Staff"),
            "email": email,
            "initials": _initials(name, email),
            "is_staff": True,
        },
        "nav_moderation_badge": int(mod_count or 0),
    }
