import pandas as pd


def find_new_reference_ids(
    df_monday_ids_existing: pd.DataFrame,
    df_base: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compara os reference_id do Rig com os IDs já existentes no Monday
    e retorna apenas os novos registros.

    Args:
        df_monday_ids_existing:
            DataFrame com coluna 'Monday ID'
        df_base:
            DataFrame com colunas ['rig_id', 'name', 'date', 'reference_id']

    Returns:
        DataFrame com colunas:
        ['rig_id', 'name', 'date', 'reference_id']
        contendo apenas os IDs novos (não existentes no Monday).
    """
    if df_monday_ids_existing is None or df_monday_ids_existing.empty:
        monday_ids_existing = pd.Series(dtype="string")
    else:
        monday_ids_existing = (
            df_monday_ids_existing["Monday ID"]
            .dropna()
            .astype("string")
        )

    if df_base is None or df_base.empty:
        return pd.DataFrame(columns=["rig_id", "name", "date", "reference_id"])

    df_rig_reference_base = df_base.copy()
    df_rig_reference_base["reference_id"] = df_rig_reference_base["reference_id"].astype("string")

    df_new_reference_ids = (
        df_rig_reference_base[
            df_rig_reference_base["reference_id"].notna()
            & ~df_rig_reference_base["reference_id"].isin(monday_ids_existing)
        ][["rig_id", "name", "date", "reference_id"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return df_new_reference_ids


if __name__ == "__main__":
    # teste rápido opcional
    df_monday_example = pd.DataFrame(
        {"Monday ID": ["SPT 111 - 2026-01-01", "SPT 60 - 2026-01-01"]}
    )

    df_base_example = pd.DataFrame(
        {
            "rig_id": ["1", "2", "3"],
            "name": ["SPT 111", "SPT 60", "SPT 76"],
            "date": ["2026-01-01", "2026-01-01", "2026-01-01"],
            "reference_id": [
                "SPT 111 - 2026-01-01",
                "SPT 60 - 2026-01-01",
                "SPT 76 - 2026-01-01",
            ],
        }
    )

    df_new_reference_ids = find_new_reference_ids(
        df_monday_ids_existing=df_monday_example,
        df_base=df_base_example,
    )

    print(df_new_reference_ids)
    print(f"Novos IDs: {len(df_new_reference_ids)}")