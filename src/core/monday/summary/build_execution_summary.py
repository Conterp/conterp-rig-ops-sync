from __future__ import annotations

import time
from typing import Any

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