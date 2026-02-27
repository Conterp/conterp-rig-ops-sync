import pandas as pd

from src.config.settings import MAX_DIAS_POR_RANGE


def build_rig_date_ranges(df_new_ids: pd.DataFrame) -> pd.DataFrame:
    """
    Cria ranges de datas por rig_id/name a partir do df_new_ids.

    Regras:
    1) Cria ranges naturais quando as datas são consecutivas.
    2) Divide cada range natural em chunks de até MAX_DIAS_POR_RANGE dias.
    3) Retorna start_date e end_date em formato YYYY-MM-DD.

    Args:
        df_new_ids:
            DataFrame com colunas ['rig_id', 'name', 'date', 'reference_id']

    Returns:
        DataFrame com colunas:
        ['rig_id', 'name', 'start_date', 'end_date', 'days']
    """
    if df_new_ids is None or df_new_ids.empty:
        return pd.DataFrame(columns=["rig_id", "name", "start_date", "end_date", "days"])

    df_new_ids_base = df_new_ids[["rig_id", "name", "date"]].copy()
    df_new_ids_base["date"] = pd.to_datetime(df_new_ids_base["date"], errors="coerce")
    df_new_ids_base = df_new_ids_base.dropna(subset=["date"])

    if df_new_ids_base.empty:
        return pd.DataFrame(columns=["rig_id", "name", "start_date", "end_date", "days"])

    df_new_ids_base = (
        df_new_ids_base
        .sort_values(["rig_id", "name", "date"])
        .reset_index(drop=True)
    )

    # 1) range natural: quebra quando não é dia consecutivo
    df_new_ids_base["is_break"] = (
        df_new_ids_base
        .groupby(["rig_id", "name"])["date"]
        .diff()
        .dt.days
        .ne(1)
        .fillna(True)
    )

    df_new_ids_base["range_group"] = (
        df_new_ids_base
        .groupby(["rig_id", "name"])["is_break"]
        .cumsum()
    )

    # 2) chunk dentro de cada range natural
    df_new_ids_base["index_within_range"] = (
        df_new_ids_base
        .groupby(["rig_id", "name", "range_group"])
        .cumcount()
    )

    df_new_ids_base["chunk_group"] = (
        df_new_ids_base["index_within_range"] // MAX_DIAS_POR_RANGE
    )

    df_ranges = (
        df_new_ids_base
        .groupby(["rig_id", "name", "range_group", "chunk_group"], as_index=False)
        .agg(
            start_date=("date", "min"),
            end_date=("date", "max"),
            days=("date", "size"),
        )
        .drop(columns=["range_group", "chunk_group"])
        .sort_values(["rig_id", "start_date"])
        .reset_index(drop=True)
    )

    # ✅ checagem de consistência
    total_days_in_ranges = int(df_ranges["days"].sum())
    total_new_days = len(df_new_ids_base)

    assert total_days_in_ranges == total_new_days, (
        f"Não bate! ranges={total_days_in_ranges} vs novos={total_new_days}"
    )

    # pronto pra params
    df_ranges["start_date"] = df_ranges["start_date"].dt.strftime("%Y-%m-%d")
    df_ranges["end_date"] = df_ranges["end_date"].dt.strftime("%Y-%m-%d")

    return df_ranges


if __name__ == "__main__":
    df_new_ids_example = pd.DataFrame(
        {
            "rig_id": ["1", "1", "1", "1", "2", "2"],
            "name": ["SPT 111", "SPT 111", "SPT 111", "SPT 111", "SPT 60", "SPT 60"],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-10", "2026-01-01", "2026-01-02"],
            "reference_id": [
                "SPT 111 - 2026-01-01",
                "SPT 111 - 2026-01-02",
                "SPT 111 - 2026-01-03",
                "SPT 111 - 2026-01-10",
                "SPT 60 - 2026-01-01",
                "SPT 60 - 2026-01-02",
            ],
        }
    )

    df_ranges = build_rig_date_ranges(df_new_ids_example)
    print(df_ranges)
    print(f"Qtd ranges: {len(df_ranges)}")
    print(f"Total dias: {int(df_ranges['days'].sum())}")