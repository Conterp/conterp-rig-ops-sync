import pandas as pd
import requests
from tqdm import tqdm

from src.config.settings import RIG_BASE_URL, RIG_TIMEOUT_S


def fetch_enrich_by_ranges(
    session: requests.Session,
    df_ranges: pd.DataFrame,
    show_progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Busca os detalhes diários por range no endpoint:
    /dashboard/rig/operational-summary

    Args:
        session:
            requests.Session com Authorization Bearer e retry/backoff
            (gerada por build_rig_session)
        df_ranges:
            DataFrame com colunas:
            ['rig_id', 'name', 'start_date', 'end_date', 'days']
        show_progress:
            True para mostrar tqdm

    Returns:
        df_rig_operational_daily:
            DataFrame bruto com válidos + erros/vazios
        df_rig_operational_daily_valid:
            DataFrame limpo, com uma linha por sonda/dia
        df_rig_operational_daily_errors:
            DataFrame apenas com erros/ranges vazios
    """
    expected_columns = [
        "rig_id",
        "Nome da Sonda",
        "Data",
        "Eficiência (%)",
        "Horas Produtivas",
        "Total de Horas",
        "Operação (Horas)",
        "DTM (Horas)",
        "Gloss (Horas)",
        "Reparo (Horas)",
        "Outros (Horas)",
        "Stand By (Horas)",
        "Parada Comercial (Horas)",
        "Parada Programada (Horas)",
        "reference_id",
        "error",
        "start_date",
        "end_date",
    ]

    if not RIG_BASE_URL:
        raise RuntimeError("RIG_BASE_URL não definido no .env")

    if df_ranges is None or df_ranges.empty:
        print("Nenhum range para processar (df_ranges vazio). Nada a baixar.")
        empty_df = pd.DataFrame(columns=expected_columns)
        return empty_df.copy(), empty_df.copy(), empty_df.copy()

    dashboard_url = f"{RIG_BASE_URL.rstrip('/')}/dashboard/rig/operational-summary"
    collected_rows: list[dict] = []

    ranges_iterator = (
        tqdm(
            df_ranges.itertuples(index=False),
            total=len(df_ranges),
            desc="⏳ Baixando detalhes por range",
            unit="range",
        )
        if show_progress
        else df_ranges.itertuples(index=False)
    )

    for range_row in ranges_iterator:
        rig_id = range_row.rig_id
        rig_name_expected = range_row.name
        start_date = range_row.start_date
        end_date = range_row.end_date

        query_params = {
            "rig_id": rig_id,
            "start_date": start_date,
            "end_date": end_date,
        }

        try:
            response = session.get(
                dashboard_url,
                params=query_params,
                timeout=(RIG_TIMEOUT_S, RIG_TIMEOUT_S),
            )
            response.raise_for_status()
            response_payload = response.json()

        except Exception as exc:
            collected_rows.append(
                {
                    "rig_id": rig_id,
                    "Nome da Sonda": rig_name_expected,
                    "Data": None,
                    "error": str(exc),
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            continue

        rig_name_from_payload = response_payload.get("rigName") or rig_name_expected
        daily_series = (response_payload.get("operationalEfficiency") or {}).get("dailySeries") or []

        if not daily_series:
            collected_rows.append(
                {
                    "rig_id": rig_id,
                    "Nome da Sonda": rig_name_from_payload,
                    "Data": None,
                    "error": "dailySeries vazio",
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            continue

        for daily_entry in daily_series:
            totals_by_kind = daily_entry.get("totalsByKind") or {}

            collected_rows.append(
                {
                    "rig_id": rig_id,
                    "Nome da Sonda": rig_name_from_payload,
                    "Data": daily_entry.get("date"),
                    "Eficiência (%)": daily_entry.get("efficiencyPercentage"),
                    "Horas Produtivas": daily_entry.get("productiveHours"),
                    "Total de Horas": daily_entry.get("totalHours"),
                    "Operação (Horas)": totals_by_kind.get("OPERATING"),
                    "DTM (Horas)": totals_by_kind.get("DTM"),
                    "Gloss (Horas)": totals_by_kind.get("GLOSS"),
                    "Reparo (Horas)": totals_by_kind.get("REPAIR"),
                    "Outros (Horas)": totals_by_kind.get("OTHER"),
                    "Stand By (Horas)": totals_by_kind.get("STAND_BY"),
                    "Parada Comercial (Horas)": totals_by_kind.get("COMMERCIAL_STOP"),
                    "Parada Programada (Horas)": totals_by_kind.get("SCHEDULED_STOP"),
                    "error": None,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

    df_rig_operational_daily = pd.DataFrame(collected_rows)

    if df_rig_operational_daily.empty:
        print("Nenhum dado retornado (collected_rows vazio).")
        df_rig_operational_daily = pd.DataFrame(columns=expected_columns)

    if {"Nome da Sonda", "Data"}.issubset(df_rig_operational_daily.columns):
        rig_name_as_string = df_rig_operational_daily["Nome da Sonda"].astype("string")
        date_as_string = df_rig_operational_daily["Data"].astype("string")

        df_rig_operational_daily["reference_id"] = pd.NA
        valid_reference_mask = rig_name_as_string.notna() & date_as_string.notna()
        df_rig_operational_daily.loc[valid_reference_mask, "reference_id"] = (
            rig_name_as_string[valid_reference_mask] + " - " + date_as_string[valid_reference_mask]
        )
    else:
        df_rig_operational_daily["reference_id"] = pd.NA

    df_rig_operational_daily_valid = (
        df_rig_operational_daily
        .dropna(subset=["Data"])
        .drop_duplicates(subset=["reference_id"])
        .reset_index(drop=True)
    )

    df_rig_operational_daily_errors = (
        df_rig_operational_daily[df_rig_operational_daily["Data"].isna()]
        .copy()
        .reset_index(drop=True)
    )

    return (
        df_rig_operational_daily,
        df_rig_operational_daily_valid,
        df_rig_operational_daily_errors,
    )


if __name__ == "__main__":
    from src.core.rig.auth import get_rig_token, build_rig_session
    from src.core.rig.fetch_rigs import fetch_rigs, rigs_to_records
    from src.utils.fetch_current_date import get_date_range_from_start
    from src.core.rig.fetch_reference_ids import fetch_reference_ids
    from src.utils.find_new_reference_ids import find_new_reference_ids
    from src.utils.build_rig_date_ranges import build_rig_date_ranges
    from src.core.monday.fetch_monday_ids import fetch_monday_ids

    rig_token = get_rig_token()
    rig_session = build_rig_session(rig_token)

    df_monday_ids_existing = fetch_monday_ids(limit=500)
    df_rigs_ids = fetch_rigs(session=rig_session)
    rigs_records = rigs_to_records(df_rigs_ids)

    start_date, end_date = get_date_range_from_start()

    df_base, df_rig_reference_id = fetch_reference_ids(
        session=rig_session,
        rigs_records=rigs_records,
        start_date=start_date,
        end_date=end_date,
        show_progress=True,
    )

    df_new_ids = find_new_reference_ids(
        df_monday_ids_existing=df_monday_ids_existing,
        df_base=df_base,
    )

    df_ranges = build_rig_date_ranges(df_new_ids)

    (
        df_rig_operational_daily,
        df_rig_operational_daily_valid,
        df_rig_operational_daily_errors,
    ) = fetch_enrich_by_ranges(
        session=rig_session,
        df_ranges=df_ranges,
        show_progress=True,
    )

    print(df_rig_operational_daily_valid)
    print(f"Linhas válidas: {len(df_rig_operational_daily_valid)}")
    print(f"Ranges com erro/vazio: {len(df_rig_operational_daily_errors)}")