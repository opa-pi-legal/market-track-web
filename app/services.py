import requests
from django.conf import settings

class LoginAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def login_with_api(username: str, password: str) -> dict:
    url = f"{settings.API_BASE_URL.rstrip('/')}/core-api/api/login/"    
    payload = {
        "username" : username,
        "password" : password,
    }
    
    try:
        response = requests.post(
            url,
            json = payload,
            headers={
                "Content":"application/json", 
                "Accept": "application/json"
            },
            timeout=5,
        )
        
        response.raise_for_status()
        return response.json()

    except requests.Timeout as exc:
        raise LoginAPIError("Authentication service time out.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        raise LoginAPIError("Invalid credentials or authentication failed.", status_code=status) from exc
    except requests.RequestException as exc:
        raise LoginAPIError("Could not reach the authentication service.") from exc
    