import pandas as pd
import requests

from src.config.settings import RIG_BASE_URL, RIG_TIMEOUT_S
from src.core.rig.auth import get_rig_token, build_rig_session


def fetch_rigs(headers: dict) -> pd.DataFrame:
    """
    Busca as sondas (rigs) no RigMgt e retorna um DataFrame com:
    - 'ID da Sonda'
    - 'Nome da Sonda'
    """
    if not RIG_BASE_URL:
        raise RuntimeError("RIG_BASE_URL não definido no .env")

    url_rigs = f"{RIG_BASE_URL.rstrip('/')}/rigs"

    response = requests.get(url_rigs, headers=headers, timeout=RIG_TIMEOUT_S)
    response.raise_for_status()

    data = response.json()
    items = data.get("items", [])

    df_rigs = pd.DataFrame(items)

    if df_rigs.empty:
        return pd.DataFrame(columns=["ID da Sonda", "Nome da Sonda"])

    df_rigs = df_rigs[["id", "name"]].copy()
    df_rigs = df_rigs.rename(columns={"id": "ID da Sonda", "name": "Nome da Sonda"})
    return df_rigs


def rigs_to_records(df_rigs: pd.DataFrame) -> list[dict]:
    """
    Converte o df_rigs para o formato:
    [{"ID da Sonda": "...", "Nome da Sonda": "..."}, ...]
    """
    if df_rigs is None or df_rigs.empty:
        return []
    return df_rigs[["ID da Sonda", "Nome da Sonda"]].to_dict(orient="records")


if __name__ == "__main__":
    # Teste rápido: autentica e imprime rigs
    token = get_rig_token()
    session = build_rig_session(token)

    df_rigs = fetch_rigs(headers=session.headers)
    print(df_rigs)
    print(f"{len(df_rigs)} rows × {df_rigs.shape[1]} columns")