import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Tuple, Set

from src.config.settings import (
    RIG_BASE_URL,
    RIG_EMAIL,
    RIG_PASSWORD,
    RIG_TIMEOUT_S,
    RIG_MAX_RETRIES,
    RIG_BACKOFF_BASE,
)

def _build_retry_for(methods: Set[str]) -> Retry:
    return Retry(
        total=RIG_MAX_RETRIES,
        connect=RIG_MAX_RETRIES,
        read=RIG_MAX_RETRIES,
        status=RIG_MAX_RETRIES,
        backoff_factor=RIG_BACKOFF_BASE,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=methods,               # ex.: {"POST"} ou {"GET"}
        respect_retry_after_header=True,
        raise_on_status=False,                 
    )

def _build_session(methods: Set[str]) -> requests.Session:
    retry_strategy = _build_retry_for(methods)
    adapter = HTTPAdapter(max_retries=retry_strategy)

    http_session = requests.Session()
    http_session.mount("https://", adapter)
    http_session.mount("http://", adapter)
    return http_session

def get_rig_token() -> str:
    """
    Faz login na API do RigMgt e retorna o accessToken.
    Usa retry/backoff e timeout baseados no settings/.env.
    """
    if not (RIG_BASE_URL and RIG_EMAIL and RIG_PASSWORD):
        raise RuntimeError("Config Rig ausente: verifique RIG_BASE_URL/RIG_EMAIL/RIG_PASSWORD no .env")

    login_url = f"{RIG_BASE_URL.rstrip('/')}/auth/sign-in"
    payload = {"email": RIG_EMAIL, "password": RIG_PASSWORD}

    http_session = _build_session({"POST"})
    timeout: Tuple[int, int] = (RIG_TIMEOUT_S, RIG_TIMEOUT_S)

    try:
        response = http_session.post(login_url, json=payload, timeout=timeout)
        if response.status_code != 200:
            body_snippet = (response.text or "")[:300]
            raise ConnectionError(f"HTTP {response.status_code} no login RigMgt. Corpo: {body_snippet}")
    except requests.exceptions.RequestException as exc:
        raise ConnectionError(f"Erro de rede ao autenticar no RigMgt: {exc}") from exc

    try:
        response_json = response.json()
    except ValueError as exc:
        raise ValueError("Resposta inválida da API (não é JSON).") from exc

    access_token = response_json.get("accessToken")
    if not access_token:
        raise ValueError("accessToken não encontrado na resposta do RigMgt.")

    print("🔓 Login no RigMgt efetuado com sucesso!")
    return access_token

def build_rig_session(access_token: str) -> requests.Session:
    """
    Retorna uma requests.Session com Authorization Bearer e retry para GETs.
    Use esta sessão nas consultas subsequentes.
    """
    if not access_token:
        raise ValueError("access_token vazio.")
    http_session = _build_session({"GET"})
    http_session.headers.update({"Authorization": f"Bearer {access_token}"})
    return http_session

if __name__ == "__main__":
    token = get_rig_token()
    print(f"Token obtido (parcial): {token[:20]}...")