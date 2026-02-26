import os
import json
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Carrega as variáveis do .env (na raiz do projeto)
load_dotenv()

# ===========================
# 🔐 Configurações RigMgt
# ===========================
RIG_BASE_URL: str = os.getenv("RIG_BASE_URL")
RIG_EMAIL: Optional[str] = os.getenv("RIG_EMAIL")
RIG_PASSWORD: Optional[str] = os.getenv("RIG_PASSWORD")
RIG_TIMEOUT_S: int = int(os.getenv("RIG_TIMEOUT_S"))

# Retry/backoff (Rig)
RIG_MAX_RETRIES: int = int(os.getenv("RIG_MAX_RETRIES"))
RIG_BACKOFF_BASE: float = float(os.getenv("RIG_BACKOFF_BASE"))
RIG_BACKOFF_CAP: float = float(os.getenv("RIG_BACKOFF_CAP"))

# ===========================
# 🔐 Configurações Monday API
# ===========================
MONDAY_BASE_URL: str = os.getenv("MONDAY_BASE_URL")
MONDAY_API_TOKEN: Optional[str] = os.getenv("MONDAY_API_TOKEN")
MONDAY_TIMEOUT_S: int = int(os.getenv("MONDAY_TIMEOUT_S"))

# Retry/backoff (Monday)
MONDAY_MAX_RETRIES: int = int(os.getenv("MONDAY_MAX_RETRIES", "8"))
MONDAY_BACKOFF_BASE: float = float(os.getenv("MONDAY_BACKOFF_BASE", "1.0"))
MONDAY_BACKOFF_CAP: float = float(os.getenv("MONDAY_BACKOFF_CAP", "60"))
MONDAY_SLEEP_BETWEEN: float = float(os.getenv("MONDAY_SLEEP_BETWEEN", "0.35"))

# ===========================
# 🗂️ Boards / Groups
# ===========================
MONDAY_BOARD_ID: Optional[int] = int(os.getenv("MONDAY_BOARD_ID")) if os.getenv("MONDAY_BOARD_ID") else None
MONDAY_GROUP_ID: str = os.getenv("MONDAY_GROUP_ID")

# ===========================
# 🧩 Monday Columns (JSON)
# ===========================
def _json_load(env_value: Optional[str], name: str) -> Any:
    """
    Carrega JSON vindo do .env (string) com erro amigável.
    Retorna None se vazio. Lança ValueError se inválido.
    """
    if env_value is None or str(env_value).strip() == "":
        return None
    try:
        return json.loads(env_value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Variável {name} contém JSON inválido: {e}") from e

# Ex.: {"data":"date4","sonda":"color_...","eficiencia":"numeric_..."}
MONDAY_COLS_JSON: Dict[str, str] = _json_load(os.getenv("MONDAY_COLS_JSON"), "MONDAY_COLS_JSON") or {}

# ===========================
# 📅 Regras do Pipeline
# ===========================
PIPELINE_TZ: str = os.getenv("PIPELINE_TZ", "America/Sao_Paulo")
PIPELINE_START_DATE: str = os.getenv("PIPELINE_START_DATE", "2024-01-01")
MAX_DIAS_POR_RANGE: int = int(os.getenv("MAX_DIAS_POR_RANGE", "10"))

# ===========================
# 🧰 Helpers de log seguro
# ===========================
def _mask_token(token: Optional[str], head: int = 4, tail: int = 3) -> str:
    if not token:
        return "MISSING"
    if len(token) <= head + tail:
        return "*" * len(token)
    return f"{token[:head]}...{token[-tail:]} (len={len(token)})"

def _preview(text: Optional[str], n: int = 40) -> str:
    if not text:
        return "MISSING"
    text_str = str(text)
    return text_str[:n] + ("..." if len(text_str) > n else "")

def _mask_id(value: Optional[int]) -> str:
    if value is None:
        return "MISSING"
    id_str = str(value)
    return (id_str[:3] + "...") if len(id_str) > 3 else id_str

def _mask_email(email: Optional[str]) -> str:
    if not email:
        return "MISSING"
    email_str = str(email)
    if "@" not in email_str:
        return "***"
    user_part, domain_part = email_str.split("@", 1)
    if len(user_part) <= 2:
        return f"{user_part[0]}***@{domain_part}"
    return f"{user_part[:2]}***@{domain_part}"

# ===========================
# 🔍 Validação opcional
# ===========================
def check_required_envs() -> None:
    """
    Valida presença das variáveis mínimas e integridade do JSON.
    Não imprime valores sensíveis, apenas quais chaves estão faltando.
    """
    missing = [
        var for var, val in [
            ("RIG_EMAIL", RIG_EMAIL),
            ("RIG_PASSWORD", RIG_PASSWORD),
            ("RIG_BASE_URL", RIG_BASE_URL),
            ("MONDAY_API_TOKEN", MONDAY_API_TOKEN),
            ("MONDAY_BASE_URL", MONDAY_BASE_URL),
            ("MONDAY_BOARD_ID", MONDAY_BOARD_ID),
            ("MONDAY_GROUP_ID", MONDAY_GROUP_ID),
            ("MONDAY_COLS_JSON", MONDAY_COLS_JSON if MONDAY_COLS_JSON else None),
            ("PIPELINE_START_DATE", PIPELINE_START_DATE),
        ]
        if not val
    ]

    if missing:
        print(f"⚠️ Atenção: variáveis ausentes/inválidas no .env → {', '.join(missing)}")
        return

    print("✅ Variáveis essenciais carregadas.")
    print(f"• Rig URL: {_preview(RIG_BASE_URL)} | Email: {_mask_email(RIG_EMAIL)} | Timeout: {RIG_TIMEOUT_S}s")
    print(f"• Rig Retry: max={RIG_MAX_RETRIES}, base={RIG_BACKOFF_BASE}, cap={RIG_BACKOFF_CAP}")
    print(f"• Monday URL: {_preview(MONDAY_BASE_URL)} | Token: {_mask_token(MONDAY_API_TOKEN)} | Timeout: {MONDAY_TIMEOUT_S}s")
    print(f"• Monday Retry: max={MONDAY_MAX_RETRIES}, base={MONDAY_BACKOFF_BASE}, cap={MONDAY_BACKOFF_CAP}, sleep={MONDAY_SLEEP_BETWEEN}")
    print(f"• Board: {_mask_id(MONDAY_BOARD_ID)} | Group: {MONDAY_GROUP_ID}")
    print(f"• Monday Cols mapeadas: {len(MONDAY_COLS_JSON)}")
    print(f"• Pipeline TZ: {PIPELINE_TZ} | Start: {PIPELINE_START_DATE} | MaxDiasRange: {MAX_DIAS_POR_RANGE}")

# ===========================
# 🧪 Execução direta (teste)
# ===========================
if __name__ == "__main__":
    try:
        check_required_envs()
    except ValueError as error:
        print(f"❌ Erro de configuração: {error}")