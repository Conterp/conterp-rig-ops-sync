import pandas as pd


def find_missing_reference_ids(
    df_rigs: pd.DataFrame,
    df_base: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Gera o DataFrame de registros faltantes (sonda x data) no intervalo [start_date, end_date].

    - Universo esperado: todas as datas do range para cada sonda em df_rigs
    - Universo válido: datas presentes em df_base (vindas da API)
    - Faltantes = esperado - válido

    Args:
        df_rigs:
            DataFrame com colunas: ["ID da Sonda", "Nome da Sonda"]
        df_base:
            DataFrame com colunas: ["rig_id", "name", "date", ...]
        start_date, end_date:
            YYYY-MM-DD

    Returns:
        DataFrame com colunas: ["rig_id", "name", "date", "reference_id"]
    """
    if df_rigs is None or df_rigs.empty:
        return pd.DataFrame(columns=["rig_id", "name", "date", "reference_id"])

    # Normaliza rigs
    rigs = df_rigs[["ID da Sonda", "Nome da Sonda"]].copy()
    rigs = rigs.rename(columns={"ID da Sonda": "rig_id", "Nome da Sonda": "name"})
    rigs["rig_id"] = rigs["rig_id"].astype("string")
    rigs["name"] = rigs["name"].astype("string")

    # Range de datas
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    df_dates = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})

    # Universo esperado: cross join rigs x dates
    rigs["_key"] = 1
    df_dates["_key"] = 1
    expected = rigs.merge(df_dates, on="_key", how="inner").drop(columns=["_key"])

    expected["reference_id"] = expected["name"] + " - " + expected["date"]

    # Universo válido (o que existe na API)
    if df_base is None or df_base.empty or "date" not in df_base.columns:
        valid = pd.DataFrame(columns=["rig_id", "date"])
    else:
        valid = df_base.copy()
        valid["rig_id"] = valid["rig_id"].astype("string")
        valid["date"] = pd.to_datetime(valid["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        valid = valid.dropna(subset=["rig_id", "date"])[["rig_id", "date"]].drop_duplicates()

    # Anti-join: esperado - válido
    missing = expected.merge(valid, on=["rig_id", "date"], how="left", indicator=True)
    missing = missing[missing["_merge"] == "left_only"].drop(columns=["_merge"])

    return missing[["rig_id", "name", "date", "reference_id"]].reset_index(drop=True)


if __name__ == "__main__":
    # Teste rápido local (sem chamar API)
    df_rigs_example = pd.DataFrame(
        {
            "ID da Sonda": ["1", "2"],
            "Nome da Sonda": ["SPT 111", "SPT 60"],
        }
    )

    # Simulando datas que "existem" na API (df_base)
    df_base_example = pd.DataFrame(
        {
            "rig_id": ["1", "2"],
            "name": ["SPT 111", "SPT 60"],
            "date": ["2026-01-01", "2026-01-02"],
        }
    )

    df_missing = find_missing_reference_ids(
        df_rigs=df_rigs_example,
        df_base=df_base_example,
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    print(df_missing.head(20))
    print("Total faltantes:", len(df_missing))