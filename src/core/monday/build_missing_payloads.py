import pandas as pd
from src.config.settings import MONDAY_COLS_JSON, MONDAY_GROUP_FALTANTES


def build_missing_payloads(df_missing_to_create: pd.DataFrame) -> list[dict]:
    """
    Constrói payloads para criação de itens no grupo 'Registros/Datas Faltantes'.

    Espera DataFrame com colunas:
    - reference_id
    - date
    - name   (Nome da Sonda)

    Retorna:
      [{"item_name": "...", "column_values": {...}, "group_id": "..."}]
    """
    missing_payloads: list[dict] = []

    if df_missing_to_create is None or df_missing_to_create.empty:
        return missing_payloads

    required_columns = {"reference_id", "date", "name"}
    missing_cols = required_columns - set(df_missing_to_create.columns)
    if missing_cols:
        raise KeyError(f"df_missing_to_create sem colunas obrigatórias: {missing_cols}")

    if not MONDAY_COLS_JSON:
        raise RuntimeError("MONDAY_COLS_JSON não definido no .env")
    if not MONDAY_GROUP_FALTANTES:
        raise RuntimeError("MONDAY_GROUP_FALTANTES não definido no .env")

    df_upload = df_missing_to_create.dropna(subset=["reference_id", "date", "name"]).copy()

    for _, row in df_upload.iterrows():
        item_name = str(row["reference_id"])

        column_values = {
            MONDAY_COLS_JSON["data"]: {"date": str(row["date"])},
            MONDAY_COLS_JSON["sonda"]: {"label": str(row["name"])},
        }

        missing_payloads.append(
            {
                "item_name": item_name,
                "column_values": column_values,
                "group_id": MONDAY_GROUP_FALTANTES,
            }
        )

    return missing_payloads