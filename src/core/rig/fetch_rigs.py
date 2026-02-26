import pandas as pd
import requests

from src.config.settings import RIG_BASE_URL, RIG_TIMEOUT_S


def fetch_rigs(session: requests.Session) -> pd.DataFrame:
    if not RIG_BASE_URL:
        raise RuntimeError("RIG_BASE_URL não definido no .env")

    url_rigs = f"{RIG_BASE_URL.rstrip('/')}/rigs"

    response = session.get(url_rigs, timeout=(RIG_TIMEOUT_S, RIG_TIMEOUT_S))
    response.raise_for_status()

    response_payload = response.json()
    rigs_items = response_payload.get("items") or []

    if not rigs_items:
        return pd.DataFrame(columns=["ID da Sonda", "Nome da Sonda"])

    df_rigs_raw = pd.DataFrame(rigs_items)
    if not {"id", "name"}.issubset(df_rigs_raw.columns):
        return pd.DataFrame(columns=["ID da Sonda", "Nome da Sonda"])

    df_rigs_result = df_rigs_raw[["id", "name"]].copy()
    df_rigs_result = df_rigs_result.rename(columns={"id": "ID da Sonda", "name": "Nome da Sonda"})
    return df_rigs_result


def rigs_to_records(df_rigs: pd.DataFrame) -> list[dict]:
    if df_rigs is None or df_rigs.empty:
        return []
    return df_rigs[["ID da Sonda", "Nome da Sonda"]].to_dict(orient="records")


if __name__ == "__main__":
    from src.core.rig.auth import get_rig_token, build_rig_session

    token = get_rig_token()
    rig_session = build_rig_session(token)

    df_rigs = fetch_rigs(session=rig_session)
    print(df_rigs)
    print(f"{len(df_rigs)} rows × {df_rigs.shape[1]} columns")