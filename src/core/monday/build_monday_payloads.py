import pandas as pd
import json
from src.config.settings import MONDAY_COLS_JSON


def to_number(value):
    """
    Converte para float quando possível.
    Aceita strings com vírgula decimal (ex: "2,99").
    Retorna None para valores vazios/inválidos.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
        # suporta decimal com vírgula
        value = value.replace(".", "").replace(",", ".") if "," in value else value

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_status_sonda(row) -> str | None:
    """
    Regras (prioridade):
    - Parada Programada > 0 => "Parada Programada"
    - Parada Comercial > 0 => "Sem contrato"
    - Eficiência > 0 => "Operando"
    """
    parada_prog = to_number(row.get("Parada Programada (Horas)")) or 0
    parada_com = to_number(row.get("Parada Comercial (Horas)")) or 0
    eficiencia = to_number(row.get("Eficiência (%)")) or 0

    if parada_prog > 0:
        return "Parada Programada"
    if parada_com > 0:
        return "Sem Contrato"
    if eficiencia > 0:
        return "Operando"
    return None


def build_monday_payloads(df_rig_operational_daily_valid: pd.DataFrame) -> list[dict]:
    """
    Constrói os payloads para criação de itens no Monday.

    Espera um DataFrame com pelo menos as colunas:
    - reference_id
    - Data
    - Nome da Sonda

    E opcionalmente:
    - Eficiência (%)
    - Horas Produtivas
    - Operação (Horas)
    - DTM (Horas)
    - Gloss (Horas)
    - Reparo (Horas)
    - Outros (Horas)
    - Stand By (Horas)
    - Parada Comercial (Horas)
    - Parada Programada (Horas)

    Returns:
        Lista de dicts no formato:
        [
          {
            "item_name": "...",
            "column_values": {...}
          },
          ...
        ]
    """
    monday_payloads: list[dict] = []

    if df_rig_operational_daily_valid is None or df_rig_operational_daily_valid.empty:
        return monday_payloads

    required_columns = {"reference_id", "Data", "Nome da Sonda"}
    missing_columns = required_columns - set(df_rig_operational_daily_valid.columns)
    if missing_columns:
        raise KeyError(f"DataFrame sem colunas obrigatórias: {missing_columns}")

    if not MONDAY_COLS_JSON:
        raise RuntimeError("MONDAY_COLS_JSON não definido no .env")

    df_upload = df_rig_operational_daily_valid.dropna(
        subset=["reference_id", "Data", "Nome da Sonda"]
    ).copy()

    for _, row in df_upload.iterrows():
        item_name = str(row["reference_id"])

        column_values = {
            MONDAY_COLS_JSON["data"]: {"date": str(row["Data"])},
            MONDAY_COLS_JSON["sonda"]: {"label": str(row["Nome da Sonda"])},

            MONDAY_COLS_JSON["eficiencia"]: to_number(row.get("Eficiência (%)")),
            MONDAY_COLS_JSON["horas_prod"]: to_number(row.get("Horas Produtivas")),
            MONDAY_COLS_JSON["oper"]: to_number(row.get("Operação (Horas)")),
            MONDAY_COLS_JSON["dtm"]: to_number(row.get("DTM (Horas)")),
            MONDAY_COLS_JSON["gloss"]: to_number(row.get("Gloss (Horas)")),
            MONDAY_COLS_JSON["reparo"]: to_number(row.get("Reparo (Horas)")),
            MONDAY_COLS_JSON["outros"]: to_number(row.get("Outros (Horas)")),
            MONDAY_COLS_JSON["standby"]: to_number(row.get("Stand By (Horas)")),
            MONDAY_COLS_JSON["parada_com"]: to_number(row.get("Parada Comercial (Horas)")),
            MONDAY_COLS_JSON["parada_prog"]: to_number(row.get("Parada Programada (Horas)")),
        }

        # Status Sonda (opcional): só seta se existir no mapeamento e se houver status calculado
        status_sonda = compute_status_sonda(row)
        status_col_id = MONDAY_COLS_JSON.get("status_sonda")
        if status_col_id and status_sonda is not None:
            column_values[status_col_id] = {"label": status_sonda}

        column_values = {
            column_id: column_value
            for column_id, column_value in column_values.items()
            if column_value is not None
        }

        monday_payloads.append(
            {
                "item_name": item_name,
                "column_values": column_values,
            }
        )

    return monday_payloads


if __name__ == "__main__":
    df_example = pd.DataFrame(
        {
            "reference_id": ["SPT 111 - 2026-02-24"],
            "Data": ["2026-02-24"],
            "Nome da Sonda": ["SPT 111"],
            "Eficiência (%)": [100],
            "Horas Produtivas": [24],
            "Operação (Horas)": [24],
            "DTM (Horas)": [0],
            "Gloss (Horas)": [0],
            "Reparo (Horas)": [0],
            "Outros (Horas)": [0],
            "Stand By (Horas)": [0],
            "Parada Comercial (Horas)": [0],
            "Parada Programada (Horas)": [0],
        }
    )

    payloads = build_monday_payloads(df_example)
    print(json.dumps(payloads, indent=2))
    print(f"Total para subir: {len(payloads)}")