from __future__ import annotations

import time
import json
from typing import Any, Dict, List

import pandas as pd

from src.config.settings import (
    MONDAY_GROUP_EFICIENCIA,
    MONDAY_GROUP_FALTANTES,
)


def _safe_len(value: Any) -> int:
    """
    Retorna a quantidade de elementos de uma lista, DataFrame ou outro objeto.

    Caso o valor seja None, retorna zero.
    """
    if value is None:
        return 0

    try:
        return int(len(value))
    except TypeError:
        return 0


def _reference_ids(
    df: pd.DataFrame | None,
    column: str = "reference_id",
) -> set[str]:
    """
    Extrai os reference_ids únicos e válidos de um DataFrame.
    """
    if df is None or df.empty:
        return set()

    if column not in df.columns:
        raise ValueError(
            f"O DataFrame informado não possui a coluna obrigatória '{column}'."
        )

    values = (
        df[column]
        .dropna()
        .astype("string")
        .str.strip()
    )

    values = values[values.ne("")]

    return set(values.tolist())


def build_df_execution_summary(
    *,
    pipeline_start_ts: float,

    # Criação de Eficiência
    monday_payloads: Any = None,
    successful_creations: Any = None,
    failed_creations: Any = None,

    # Criação de Datas Faltantes
    missing_payloads: Any = None,
    successful_missing: Any = None,
    failed_missing: Any = None,

    # Duplicados de Eficiência
    item_ids_to_delete: Any = None,
    successful_deletions: Any = None,
    failed_deletions: Any = None,

    # Duplicados de Datas Faltantes
    ids_del_falt: Any = None,
    successful_del_falt: Any = None,
    failed_del_falt: Any = None,

    # Órfãos de Datas Faltantes
    item_ids_to_delete_noise: Any = None,
    successful_noise_del: Any = None,
    failed_noise_del: Any = None,

    # Órfãos de Eficiência
    orphan_item_ids_to_delete: Any = None,
    successful_orphan_deletions: Any = None,
    failed_orphan_deletions: Any = None,

    # Registros faltantes que passaram a ter dados
    item_ids_to_remove_from_faltantes: Any = None,
    successful_rm_faltantes: Any = None,
    failed_rm_faltantes: Any = None,
) -> pd.DataFrame:
    """
    Monta o resumo das ações executadas pelo Rig Ops Sync.

    DELETE DUPLICATES:
        Soma os duplicados de Eficiência e Datas Faltantes.

    DELETE ORPHANS:
        Soma os órfãos de Eficiência e Datas Faltantes.
    """

    rows = [
        {
            "ACTION": "CREATE EFFICIENCY ITEMS",
            "PLANNED": _safe_len(monday_payloads),
            "SUCCESS": _safe_len(successful_creations),
            "ERROR": _safe_len(failed_creations),
        },
        {
            "ACTION": "CREATE MISSING ITEMS",
            "PLANNED": _safe_len(missing_payloads),
            "SUCCESS": _safe_len(successful_missing),
            "ERROR": _safe_len(failed_missing),
        },
        {
            "ACTION": "DELETE DUPLICATES",
            "PLANNED": (
                _safe_len(item_ids_to_delete)
                + _safe_len(ids_del_falt)
            ),
            "SUCCESS": (
                _safe_len(successful_deletions)
                + _safe_len(successful_del_falt)
            ),
            "ERROR": (
                _safe_len(failed_deletions)
                + _safe_len(failed_del_falt)
            ),
        },
        {
            "ACTION": "DELETE ORPHANS",
            "PLANNED": (
                _safe_len(item_ids_to_delete_noise)
                + _safe_len(orphan_item_ids_to_delete)
            ),
            "SUCCESS": (
                _safe_len(successful_noise_del)
                + _safe_len(successful_orphan_deletions)
            ),
            "ERROR": (
                _safe_len(failed_noise_del)
                + _safe_len(failed_orphan_deletions)
            ),
        },
        {
            "ACTION": "REMOVE RECOVERED ITEMS",
            "PLANNED": _safe_len(
                item_ids_to_remove_from_faltantes
            ),
            "SUCCESS": _safe_len(
                successful_rm_faltantes
            ),
            "ERROR": _safe_len(
                failed_rm_faltantes
            ),
        },
    ]

    df_summary = pd.DataFrame(
        rows,
        columns=[
            "ACTION",
            "PLANNED",
            "SUCCESS",
            "ERROR",
        ],
    )

    df_summary.insert(
        0,
        "STEP",
        range(len(df_summary)),
    )

    elapsed_seconds = max(
        0,
        int(time.time() - pipeline_start_ts),
    )

    duration_text = (
        f"{elapsed_seconds // 60}m "
        f"{elapsed_seconds % 60}s"
    )

    duration_row = pd.DataFrame(
        [
            {
                "STEP": len(df_summary),
                "ACTION": "PIPELINE DURATION",
                "PLANNED": duration_text,
                "SUCCESS": "",
                "ERROR": "",
            }
        ]
    )

    return pd.concat(
        [
            df_summary,
            duration_row,
        ],
        ignore_index=True,
    )


def build_df_reconciliation(
    *,
    df_rig_reference_id: pd.DataFrame | None,
    df_missing: pd.DataFrame | None,
    df_monday_final: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Compara a quantidade esperada com a quantidade final no Monday.

    EXPECTED_ROWS:
        Registros com eficiência + registros sem dados.

    ACTUAL_ROWS:
        Total encontrado nos grupos Eficiência e Datas Faltantes.

    DELTA:
        ACTUAL_ROWS - EXPECTED_ROWS.
    """

    efficiency_reference_ids = _reference_ids(
        df_rig_reference_id
    )

    missing_reference_ids = _reference_ids(
        df_missing
    )

    expected_reference_ids = (
        efficiency_reference_ids
        | missing_reference_ids
    )

    expected_rows = len(expected_reference_ids)

    if df_monday_final is None or df_monday_final.empty:
        actual_rows = 0

    else:
        if "group_id" not in df_monday_final.columns:
            raise ValueError(
                "df_monday_final não possui a coluna "
                "obrigatória 'group_id'."
            )

        managed_groups = {
            MONDAY_GROUP_EFICIENCIA,
            MONDAY_GROUP_FALTANTES,
        }

        actual_rows = int(
            df_monday_final["group_id"]
            .astype("string")
            .isin(managed_groups)
            .sum()
        )

    delta = actual_rows - expected_rows

    return pd.DataFrame(
        [
            {
                "DESTINO_KEY": "RIG_OPS",
                "EXPECTED_ROWS": expected_rows,
                "ACTUAL_ROWS": actual_rows,
                "DELTA": delta,
            }
        ],
        columns=[
            "DESTINO_KEY",
            "EXPECTED_ROWS",
            "ACTUAL_ROWS",
            "DELTA",
        ],
    )


def _df_to_records(
    df: pd.DataFrame | None,
) -> List[Dict[str, Any]]:
    """
    Converte um DataFrame em uma lista de dicionários segura para JSON.
    """
    if df is None or df.empty:
        return []

    df_safe = df.astype(object).where(
        pd.notnull(df),
        None,
    )

    return df_safe.to_dict(orient="records")


def _to_number(value: Any) -> int:
    """
    Converte um valor em inteiro.

    Valores vazios, como o campo de duração, retornam zero.
    """
    if value in (None, ""):
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _find_by_action(
    records: List[Dict[str, Any]],
    action: str,
) -> Dict[str, Any]:
    """
    Localiza uma linha do resumo pelo nome da ação.
    """
    return next(
        (
            item
            for item in records
            if item.get("ACTION") == action
        ),
        {},
    )


def _find_by_destino(
    records: List[Dict[str, Any]],
    destino_key: str,
) -> Dict[str, Any]:
    """
    Localiza uma linha da reconciliação pelo destino.
    """
    return next(
        (
            item
            for item in records
            if item.get("DESTINO_KEY") == destino_key
        ),
        {},
    )


def _get_action_metric(
    records: List[Dict[str, Any]],
    action: str,
    metric: str,
) -> int:
    """
    Retorna uma métrica PLANNED, SUCCESS ou ERROR de uma ação.
    """
    item = _find_by_action(
        records,
        action,
    )

    return _to_number(
        item.get(metric)
    )


def _get_destino_metric(
    records: List[Dict[str, Any]],
    destino_key: str,
    metric: str,
) -> int:
    """
    Retorna uma métrica da reconciliação.
    """
    item = _find_by_destino(
        records,
        destino_key,
    )

    return _to_number(
        item.get(metric)
    )


def build_summary_payload(
    df_execution_summary: pd.DataFrame,
    df_reconciliation_summary: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Monta o payload que será enviado ao webhook do n8n.

    O n8n receberá:
    - as tabelas completas do resumo;
    - os indicadores individuais de cada ação;
    - os totais da execução;
    - a reconciliação final do board;
    - indicadores de erro e divergência.
    """

    execution_summary = _df_to_records(
        df_execution_summary
    )

    reconciliation_summary = _df_to_records(
        df_reconciliation_summary
    )

    execution_rows = [
        item
        for item in execution_summary
        if item.get("ACTION") != "PIPELINE DURATION"
    ]

    pipeline_duration = _find_by_action(
        execution_summary,
        "PIPELINE DURATION",
    ).get("PLANNED", "")

    return {
        "pipeline": "rig_ops",

        "execution_summary": execution_summary,
        "reconciliation_summary": reconciliation_summary,

        "create_efficiency_items_planned": _get_action_metric(
            execution_summary,
            "CREATE EFFICIENCY ITEMS",
            "PLANNED",
        ),
        "create_efficiency_items_success": _get_action_metric(
            execution_summary,
            "CREATE EFFICIENCY ITEMS",
            "SUCCESS",
        ),
        "create_efficiency_items_error": _get_action_metric(
            execution_summary,
            "CREATE EFFICIENCY ITEMS",
            "ERROR",
        ),

        "create_missing_items_planned": _get_action_metric(
            execution_summary,
            "CREATE MISSING ITEMS",
            "PLANNED",
        ),
        "create_missing_items_success": _get_action_metric(
            execution_summary,
            "CREATE MISSING ITEMS",
            "SUCCESS",
        ),
        "create_missing_items_error": _get_action_metric(
            execution_summary,
            "CREATE MISSING ITEMS",
            "ERROR",
        ),

        "delete_duplicates_planned": _get_action_metric(
            execution_summary,
            "DELETE DUPLICATES",
            "PLANNED",
        ),
        "delete_duplicates_success": _get_action_metric(
            execution_summary,
            "DELETE DUPLICATES",
            "SUCCESS",
        ),
        "delete_duplicates_error": _get_action_metric(
            execution_summary,
            "DELETE DUPLICATES",
            "ERROR",
        ),

        "delete_orphans_planned": _get_action_metric(
            execution_summary,
            "DELETE ORPHANS",
            "PLANNED",
        ),
        "delete_orphans_success": _get_action_metric(
            execution_summary,
            "DELETE ORPHANS",
            "SUCCESS",
        ),
        "delete_orphans_error": _get_action_metric(
            execution_summary,
            "DELETE ORPHANS",
            "ERROR",
        ),

        "remove_recovered_items_planned": _get_action_metric(
            execution_summary,
            "REMOVE RECOVERED ITEMS",
            "PLANNED",
        ),
        "remove_recovered_items_success": _get_action_metric(
            execution_summary,
            "REMOVE RECOVERED ITEMS",
            "SUCCESS",
        ),
        "remove_recovered_items_error": _get_action_metric(
            execution_summary,
            "REMOVE RECOVERED ITEMS",
            "ERROR",
        ),

        "pipeline_duration": pipeline_duration,

        "execution_total_planned": sum(
            _to_number(item.get("PLANNED"))
            for item in execution_rows
        ),
        "execution_total_success": sum(
            _to_number(item.get("SUCCESS"))
            for item in execution_rows
        ),
        "execution_total_error": sum(
            _to_number(item.get("ERROR"))
            for item in execution_rows
        ),
        "execution_has_error": any(
            _to_number(item.get("ERROR")) > 0
            for item in execution_rows
        ),

        "rig_ops_expected_rows": _get_destino_metric(
            reconciliation_summary,
            "RIG_OPS",
            "EXPECTED_ROWS",
        ),
        "rig_ops_actual_rows": _get_destino_metric(
            reconciliation_summary,
            "RIG_OPS",
            "ACTUAL_ROWS",
        ),
        "rig_ops_delta": _get_destino_metric(
            reconciliation_summary,
            "RIG_OPS",
            "DELTA",
        ),

        "reconciliation_total_expected_rows": sum(
            _to_number(item.get("EXPECTED_ROWS"))
            for item in reconciliation_summary
        ),
        "reconciliation_total_actual_rows": sum(
            _to_number(item.get("ACTUAL_ROWS"))
            for item in reconciliation_summary
        ),
        "reconciliation_total_delta": sum(
            _to_number(item.get("DELTA"))
            for item in reconciliation_summary
        ),
        "reconciliation_has_divergence": any(
            _to_number(item.get("DELTA")) != 0
            for item in reconciliation_summary
        ),
    }

if __name__ == "__main__":
    from src.core.webhook.send_to_n8n import send_summary_to_n8n

    df_summary_test = pd.DataFrame(
        [
            {
                "STEP": 0,
                "ACTION": "CREATE EFFICIENCY ITEMS",
                "PLANNED": 2,
                "SUCCESS": 2,
                "ERROR": 0,
            },
            {
                "STEP": 1,
                "ACTION": "CREATE MISSING ITEMS",
                "PLANNED": 10,
                "SUCCESS": 10,
                "ERROR": 0,
            },
            {
                "STEP": 2,
                "ACTION": "DELETE DUPLICATES",
                "PLANNED": 0,
                "SUCCESS": 0,
                "ERROR": 0,
            },
            {
                "STEP": 3,
                "ACTION": "DELETE ORPHANS",
                "PLANNED": 0,
                "SUCCESS": 0,
                "ERROR": 0,
            },
            {
                "STEP": 4,
                "ACTION": "REMOVE RECOVERED ITEMS",
                "PLANNED": 0,
                "SUCCESS": 0,
                "ERROR": 0,
            },
            {
                "STEP": 5,
                "ACTION": "PIPELINE DURATION",
                "PLANNED": "1m 39s",
                "SUCCESS": "",
                "ERROR": "",
            },
        ]
    )

    df_reconciliation_test = pd.DataFrame(
        [
            {
                "DESTINO_KEY": "RIG_OPS",
                "EXPECTED_ROWS": 5610,
                "ACTUAL_ROWS": 5610,
                "DELTA": 0,
            }
        ]
    )

    payload_test = build_summary_payload(
        df_execution_summary=df_summary_test,
        df_reconciliation_summary=df_reconciliation_test,
    )

    print("Payload de teste:")
    print(json.dumps(payload_test, indent=2, ensure_ascii=False))

    send_summary_to_n8n(payload_test)