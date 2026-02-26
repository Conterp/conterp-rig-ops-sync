import pandas as pd
import requests
from tqdm import tqdm

from src.config.settings import RIG_BASE_URL, RIG_TIMEOUT_S


def fetch_reference_ids(
    session: requests.Session,
    rigs_records: list[dict],
    start_date: str,
    end_date: str,
    show_progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Para cada rig_id, chama /dashboard/rig/operational-summary e extrai:
    - rig_id
    - rigName
    - date (dailySeries)
    e monta reference_id = "Nome - Data".

    Returns:
        df_base: colunas [rig_id, name, date, reference_id, error_status]
        df_rig_reference_id: colunas [reference_id] único
    """
    if not RIG_BASE_URL:
        raise RuntimeError("RIG_BASE_URL não definido no .env")

    dashboard_url = f"{RIG_BASE_URL.rstrip('/')}/dashboard/rig/operational-summary"
    collected_rows: list[dict] = []

    rigs_iterator = (
        tqdm(rigs_records, desc="🛠️ Criando 'reference_id'", unit="rig")
        if show_progress
        else rigs_records
    )

    for rig_record in rigs_iterator:
        rig_id = rig_record.get("ID da Sonda")
        if not rig_id:
            collected_rows.append(
                {"rig_id": None, "name": None, "date": None, "error_status": "rig_id ausente"}
            )
            continue

        query_params = {"rig_id": rig_id, "start_date": start_date, "end_date": end_date}

        try:
            response = session.get(
                dashboard_url,
                params=query_params,
                timeout=(RIG_TIMEOUT_S, RIG_TIMEOUT_S),
            )
        except requests.RequestException as exc:
            collected_rows.append(
                {"rig_id": rig_id, "name": None, "date": None, "error_status": str(exc)}
            )
            continue

        if response.status_code != 200:
            collected_rows.append(
                {"rig_id": rig_id, "name": None, "date": None, "error_status": response.status_code}
            )
            continue

        response_payload = response.json()

        rig_id_from_payload = response_payload.get("rigId", rig_id)
        rig_name_from_payload = response_payload.get("rigName")

        daily_series = (response_payload.get("operationalEfficiency") or {}).get("dailySeries") or []

        # Se vier vazio, ainda registra a sonda (sem data)
        if not daily_series:
            collected_rows.append(
                {"rig_id": rig_id_from_payload, "name": rig_name_from_payload, "date": None, "error_status": None}
            )
            continue

        for daily_series_entry in daily_series:
            collected_rows.append(
                {
                    "rig_id": rig_id_from_payload,
                    "name": rig_name_from_payload,
                    "date": daily_series_entry.get("date"),
                    "error_status": None,
                }
            )

    # garante colunas mesmo se vier vazio
    df_base = pd.DataFrame(collected_rows, columns=["rig_id", "name", "date", "error_status"])

    if df_base.empty:
        df_base["reference_id"] = pd.Series(dtype="string")
        df_rig_reference_id = pd.DataFrame(columns=["reference_id"])
        return df_base, df_rig_reference_id

    # reference_id vetorizado (sem apply)
    name_str = df_base["name"].astype("string")
    date_str = df_base["date"].astype("string")

    df_base["reference_id"] = pd.NA
    valid_mask = name_str.notna() & date_str.notna()
    df_base.loc[valid_mask, "reference_id"] = name_str[valid_mask] + " - " + date_str[valid_mask]

    df_rig_reference_id = (
        df_base[["reference_id"]]
        .dropna()
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return df_base, df_rig_reference_id

if __name__ == "__main__":
    from src.core.rig.auth import get_rig_token, build_rig_session
    from src.core.rig.fetch_rigs import fetch_rigs, rigs_to_records
    from src.utils.fetch_current_date import get_date_range_from_start

    start_date, end_date = get_date_range_from_start()

    rig_token = get_rig_token()
    rig_session = build_rig_session(rig_token)

    df_rigs = fetch_rigs(session=rig_session)
    rigs_records = rigs_to_records(df_rigs)

    df_base, df_rig_reference_id = fetch_reference_ids(
        session=rig_session,
        rigs_records=rigs_records,
        start_date=start_date,
        end_date=end_date,
        show_progress=True,
    )

    print(df_base)
    print(df_rig_reference_id)