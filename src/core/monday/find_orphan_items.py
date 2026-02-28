import pandas as pd


def find_monday_orphans(
    df_rig_reference_id: pd.DataFrame,
    df_monday_all_items: pd.DataFrame,
) -> tuple[pd.DataFrame, list[int]]:
    """
    Identifica itens órfãos no Monday.

    Regra:
    - órfão = item que existe no Monday, mas cujo reference_id_monday
      não existe mais no conjunto válido vindo da API do Rig.

    Args:
        df_rig_reference_id:
            DataFrame com coluna:
            - reference_id

        df_monday_all_items:
            DataFrame com colunas:
            - item_id
            - reference_id_monday

    Returns:
        df_monday_orphans:
            DataFrame contendo os itens órfãos encontrados no Monday

        orphan_item_ids_to_delete:
            Lista de item_id a serem excluídos
    """
    if df_rig_reference_id is None or df_rig_reference_id.empty:
        valid_rig_reference_ids = set()
    else:
        df_rig_reference_base = df_rig_reference_id.copy()
        df_rig_reference_base["reference_id"] = df_rig_reference_base["reference_id"].astype("string")
        valid_rig_reference_ids = set(df_rig_reference_base["reference_id"].dropna())

    if df_monday_all_items is None or df_monday_all_items.empty:
        empty_orphans = pd.DataFrame(columns=["item_id", "reference_id_monday"])
        return empty_orphans, []

    df_monday_valid = df_monday_all_items.copy()
    df_monday_valid["reference_id_monday"] = df_monday_valid["reference_id_monday"].astype("string")
    df_monday_valid = df_monday_valid.dropna(subset=["reference_id_monday"]).copy()

    df_monday_orphans = (
        df_monday_valid[
            ~df_monday_valid["reference_id_monday"].isin(valid_rig_reference_ids)
        ]
        .copy()
        .reset_index(drop=True)
    )

    if df_monday_orphans.empty:
        return df_monday_orphans, []

    orphan_item_ids_to_delete = (
        df_monday_orphans["item_id"]
        .astype("int64")
        .tolist()
    )

    return df_monday_orphans, orphan_item_ids_to_delete


if __name__ == "__main__":
    df_rig_reference_id_example = pd.DataFrame(
        {
            "reference_id": [
                "SPT 111 - 2026-02-24",
                "SPT 151 - 2026-02-24",
            ]
        }
    )

    df_monday_all_items_example = pd.DataFrame(
        {
            "item_id": [1, 2, 3],
            "reference_id_monday": [
                "SPT 111 - 2026-02-24",
                "SPT 151 - 2026-02-24",
                "SPT 60 - 2026-02-24",
            ],
        }
    )

    df_monday_orphans, orphan_item_ids_to_delete = find_monday_orphans(
        df_rig_reference_id=df_rig_reference_id_example,
        df_monday_all_items=df_monday_all_items_example,
    )

    print(df_monday_orphans)
    print("Órfãos encontrados:", len(df_monday_orphans))
    print("IDs para deletar:", orphan_item_ids_to_delete)