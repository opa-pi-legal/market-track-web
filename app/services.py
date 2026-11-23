import time
import requests
from django.conf import settings


class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _base_url() -> str:
    return settings.API_BASE_URL.rstrip("/")


def _headers(token: str | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_list(data) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return [item for item in data["results"] if isinstance(item, dict)]
    return []


def _extract_error(response: requests.Response, fallback: str) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            if "detail" in data:
                return str(data["detail"])
            parts = []
            for key, val in data.items():
                if isinstance(val, list) and val:
                    parts.append(f"{key}: {val[0]}")
                elif isinstance(val, str):
                    parts.append(f"{key}: {val}")
            if parts:
                return " | ".join(parts)
    except Exception:
        pass
    return fallback


def api_request(
    method: str,
    path: str,
    token: str | None = None,
    params: dict | None = None,
    payload: dict | None = None,
    timeout: float = 6.0,
):
    url = f"{_base_url()}{path}"
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=_headers(token),
            params=params,
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise APIError("Tempo limite excedido ao comunicar com a API.") from exc
    except requests.RequestException as exc:
        raise APIError("Não foi possível conectar ao servidor da API.") from exc

    if response.status_code == 204:
        return None

    if not response.ok:
        raise APIError(
            _extract_error(response, f"Erro na API (HTTP {response.status_code})."),
            status_code=response.status_code,
        )

    try:
        return response.json()
    except ValueError:
        return response.text


def safe_get_list(path: str, token: str, params: dict | None = None) -> list[dict]:
    try:
        return _extract_list(api_request("GET", path, token=token, params=params))
    except APIError:
        return []


# ---------------------------------------------------------------------------
# Autenticação & Usuário
# ---------------------------------------------------------------------------

def login_with_api(username: str, password: str) -> dict:
    payload = {
        "username": username,
        "email": username,
        "password": password,
    }
    return api_request("POST", "/core-api/api/login/", payload=payload)


def verify_firebase_id_token(id_token: str) -> dict:
    api_key = getattr(settings, "FIREBASE_API_KEY", "").strip()
    if not api_key:
        raise APIError("Chave Firebase não configurada no servidor.")
    if not id_token or not id_token.strip():
        raise APIError("Token do Google inválido ou ausente.")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    try:
        resp = requests.post(url, json={"idToken": id_token.strip()}, timeout=8.0)
    except requests.RequestException as exc:
        raise APIError("Não foi possível validar o login Google no Firebase.") from exc

    if not resp.ok:
        raise APIError("Sessão Google inválida ou expirada. Tente entrar novamente.")

    data = resp.json()
    users = data.get("users") or []
    if not users:
        raise APIError("Conta Google não encontrada.")

    user_info = users[0]
    email = (user_info.get("email") or "").strip().lower()
    if not email:
        raise APIError("Não foi possível obter o e-mail da conta Google.")

    return {
        "email": email,
        "display_name": (user_info.get("displayName") or email.split("@")[0]).strip(),
        "photo_url": user_info.get("photoUrl") or None,
        "email_verified": bool(user_info.get("emailVerified", False)),
    }


def google_login_with_api(
    email: str,
    username: str = "",
    photo_url: str | None = None,
    staff_only: bool = True,
) -> dict:
    payload: dict = {
        "email": email.strip().lower(),
        "username": (username or email.split("@")[0]).strip(),
        "display_name": (username or email.split("@")[0]).strip(),
        "staff_only": staff_only,
    }
    if photo_url:
        payload["photo_url"] = photo_url
    return api_request("POST", "/core-api/api/google-login/", payload=payload)


def register_with_api(
    username: str,
    email: str,
    password: str,
    password2: str,
    photo_url: str = "",
) -> dict:
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "password2": password2,
        "photoUrl": photo_url,
        "photo_url": photo_url or None,
    }
    return api_request("POST", "/core-api/api/register/", payload=payload)


def get_current_user(token: str) -> dict | None:
    try:
        data = api_request("GET", "/core-api/api/users/me/", token=token)
        return data if isinstance(data, dict) else None
    except APIError:
        return None


def get_users(token: str) -> list[dict]:
    return safe_get_list("/core-api/api/users/", token)


def get_staff_users(token: str) -> list[dict]:
    return safe_get_list("/core-api/api/users/staff/", token)


def create_staff_user(token: str, email: str, username: str = "", password: str = "") -> dict:
    payload: dict = {"email": email.strip().lower()}
    if username.strip():
        payload["username"] = username.strip()
    if password:
        payload["password"] = password
    return api_request("POST", "/core-api/api/users/create-staff/", token=token, payload=payload)


# ---------------------------------------------------------------------------
# Grupos & Listas de Compras
# ---------------------------------------------------------------------------

def get_groups(token: str, all_groups: bool = False) -> list[dict]:
    params = {"all_groups": "true"} if all_groups else None
    return safe_get_list("/core-api/api/groups/", token, params=params)


def get_group_members(token: str, group_id, all_groups: bool = False) -> list[dict]:
    params: dict[str, str] = {"group": str(group_id)}
    if all_groups:
        params["all_groups"] = "true"
    return safe_get_list("/core-api/api/user-groups/", token, params=params)


def remove_group_member(token: str, membership_id) -> None:
    api_request("DELETE", f"/core-api/api/user-groups/{membership_id}/", token=token)


def get_shopping_lists(
    token: str,
    group_id=None,
    all_groups: bool = False,
    query: str = "",
) -> list[dict]:
    params: dict[str, str] = {}
    if all_groups:
        params["all_groups"] = "true"
    if group_id:
        params["group"] = str(group_id)
    if query:
        params["q"] = query
    return safe_get_list("/core-api/api/shopping-lists/", token, params=params or None)


def get_shopping_list(token: str, list_id, all_groups: bool = False) -> dict | None:
    params = {"all_groups": "true"} if all_groups else None
    try:
        data = api_request(
            "GET",
            f"/core-api/api/shopping-lists/{list_id}/",
            token=token,
            params=params,
        )
        return data if isinstance(data, dict) else None
    except APIError:
        return None


def delete_shopping_list(token: str, list_id) -> None:
    api_request("DELETE", f"/core-api/api/shopping-lists/{list_id}/", token=token)


def get_shopping_list_items(token: str, list_id, all_groups: bool = False) -> list[dict]:
    params: dict[str, str] = {"shopping_list": str(list_id)}
    if all_groups:
        params["all_groups"] = "true"
    return safe_get_list(
        "/core-api/api/shopping-list-items/",
        token,
        params=params,
    )


def delete_shopping_list_item(token: str, item_id) -> None:
    api_request("DELETE", f"/core-api/api/shopping-list-items/{item_id}/", token=token)


# ---------------------------------------------------------------------------
# Ofertas da Comunidade, Alertas, Preços e Atividades
# ---------------------------------------------------------------------------

def get_community_offers(
    token: str,
    moderation_status: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    params = {
        "scope": "community",
        "active_only": "true" if active_only else "false",
    }
    if moderation_status:
        params["moderation_status"] = moderation_status
    return safe_get_list("/core-api/api/community-offers/", token, params=params)


def create_community_offer(token: str, payload: dict) -> dict:
    return api_request("POST", "/core-api/api/community-offers/", token=token, payload=payload)


def moderate_offer(token: str, offer_id, action: str) -> dict:
    return api_request(
        "POST",
        f"/core-api/api/community-offers/{offer_id}/moderate/",
        token=token,
        payload={"action": action},
    )


def get_price_alerts(token: str, unread_only: bool = False) -> list[dict]:
    params = {"unread_only": "true" if unread_only else "false"}
    return safe_get_list("/core-api/api/price-alerts/", token, params=params)


def get_price_records(token: str, group_id=None) -> list[dict]:
    params = {"group": str(group_id)} if group_id else None
    return safe_get_list("/core-api/api/price-records/", token, params=params)


def get_activity_logs(token: str, group_id=None) -> list[dict]:
    params = {"group": str(group_id)} if group_id else None
    return safe_get_list("/core-api/api/activity-logs/", token, params=params)


# ---------------------------------------------------------------------------
# Produtos (product-api) & Mercados (market-api)
# ---------------------------------------------------------------------------

def get_products(
    token: str,
    group_id=None,
    all_groups: bool = False,
    include_global: bool = True,
    query: str = "",
) -> list[dict]:
    params: dict[str, str] = {}
    if all_groups:
        params["all_groups"] = "true"
    elif group_id:
        params["group_id"] = str(group_id)
        params["include_global"] = "true" if include_global else "false"
    else:
        params["global_only"] = "true"
    if query:
        params["q"] = query
    return safe_get_list("/product-api/api/products/", token, params=params)


def get_product(token: str, product_id) -> dict | None:
    try:
        data = api_request("GET", f"/product-api/api/products/{product_id}/", token=token)
        return data if isinstance(data, dict) else None
    except APIError:
        return None


def create_product(token: str, payload: dict) -> dict:
    return api_request(
        "POST",
        "/product-api/api/products/",
        token=token,
        payload=payload,
    )


def update_product(token: str, product_id, payload: dict) -> dict:
    return api_request(
        "PATCH",
        f"/product-api/api/products/{product_id}/",
        token=token,
        payload=payload,
    )


def delete_product(token: str, product_id) -> None:
    api_request("DELETE", f"/product-api/api/products/{product_id}/", token=token)


def promote_product_global(token: str, product_id) -> dict:
    return api_request(
        "POST",
        f"/product-api/api/products/{product_id}/promote-global/",
        token=token,
        payload={"verified_source": "admin"},
    )


def get_markets(
    token: str,
    group_id=None,
    all_groups: bool = False,
    query: str = "",
) -> list[dict]:
    params: dict[str, str] = {}
    if all_groups:
        params["all_groups"] = "true"
    elif group_id:
        params["group_id"] = str(group_id)
    if query:
        params["q"] = query
    return safe_get_list("/market-api/api/market/", token, params=params)


def create_market(token: str, payload: dict) -> dict:
    return api_request(
        "POST",
        "/market-api/api/market/",
        token=token,
        payload=payload,
    )


def update_market(token: str, market_id, payload: dict) -> dict:
    return api_request(
        "PATCH",
        f"/market-api/api/market/{market_id}/",
        token=token,
        payload=payload,
    )


def delete_market(token: str, market_id) -> None:
    api_request("DELETE", f"/market-api/api/market/{market_id}/", token=token)


# ---------------------------------------------------------------------------
# Healthchecks (Manutenção)
# ---------------------------------------------------------------------------

def check_services_health() -> list[dict]:
    endpoints = [
        ("Core API", "/core-api/health/"),
        ("Market API", "/market-api/health/"),
        ("Product API", "/product-api/health/"),
    ]
    results = []
    for name, path in endpoints:
        url = f"{_base_url()}{path}"
        start = time.monotonic()
        try:
            resp = requests.get(url, timeout=2.5)
            latency_ms = int(round((time.monotonic() - start) * 1000))
            results.append(
                {
                    "name": name,
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "endpoint": path,
                    "detail": "Operacional" if resp.status_code == 200 else f"HTTP {resp.status_code}",
                }
            )
        except requests.RequestException:
            latency_ms = int(round((time.monotonic() - start) * 1000))
            results.append(
                {
                    "name": name,
                    "ok": False,
                    "status_code": None,
                    "latency_ms": latency_ms,
                    "endpoint": path,
                    "detail": "Indisponível",
                }
            )
    return results


def get_rabbitmq_queues() -> list[dict]:
    """
    Consulta a API HTTP de Management do RabbitMQ (15672) na rede Docker interna
    ou localhost para exibir o estado real das filas na tela de Manutenção.
    """
    import os

    rmq_user = os.getenv("RABBITMQ_USER", "guest")
    rmq_pass = os.getenv("RABBITMQ_PASS", "guest")
    candidates = [
        os.getenv("RABBITMQ_MGMT_URL", "").rstrip("/"),
        "http://rabbitmq:15672",
        "http://127.0.0.1:15672",
    ]
    descriptions = {
        "core_api.events": "Processa ofertas publicadas, dispara alertas de preço (PriceAlert) e grava logs de auditoria.",
        "product_api.group_events": "Sincroniza exclusão de grupos limpando produtos privados (preserva Catálogo Global).",
        "market_api.group_events": "Sincroniza exclusão de grupos limpando mercados privados daquele grupo.",
    }

    for base in candidates:
        if not base:
            continue
        try:
            resp = requests.get(
                f"{base}/api/queues",
                auth=(rmq_user, rmq_pass),
                timeout=2.0,
            )
            if not resp.ok:
                continue
            raw_list = resp.json()
            if not isinstance(raw_list, list):
                continue
            queues = []
            for q in raw_list:
                if not isinstance(q, dict):
                    continue
                name = str(q.get("name") or "")
                stats = q.get("message_stats") if isinstance(q.get("message_stats"), dict) else {}
                state = str(q.get("state") or "running").lower()
                consumers = int(q.get("consumers") or 0)
                queues.append(
                    {
                        "name": name,
                        "vhost": q.get("vhost") or "/",
                        "state": state,
                        "ok": state == "running" and consumers > 0,
                        "consumers": consumers,
                        "messages_ready": int(q.get("messages_ready") or 0),
                        "messages_unack": int(q.get("messages_unacknowledged") or 0),
                        "messages_total": int(q.get("messages") or 0),
                        "published_total": int(stats.get("publish") or 0),
                        "delivered_total": int(stats.get("deliver_get") or stats.get("deliver") or 0),
                        "acked_total": int(stats.get("ack") or 0),
                        "description": descriptions.get(name, "Fila de eventos assíncronos do domínio."),
                    }
                )
            queues.sort(key=lambda item: item["name"])
            return queues
        except requests.RequestException:
            continue
    return []
