import pandas as pd


def find_monday_duplicates(
    df_monday_all_items: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Identifica duplicados no Monday com base em 'reference_id_monday'.

    Args:
        df_monday_all_items:
            DataFrame com colunas:
            - item_id
            - reference_id_monday

    Returns:
        df_monday_duplicates:
            Todas as linhas duplicadas (inclusive a primeira ocorrência),
            ordenadas por reference_id_monday e item_id.

        df_duplicate_summary:
            Resumo por reference_id_monday com quantidade de ocorrências.
            Exemplo:
            reference_id_monday | qtd_duplicados
            SPT 111 - 2026-02-24 | 2
    """
    if df_monday_all_items is None or df_monday_all_items.empty:
        empty_duplicates = pd.DataFrame(columns=["item_id", "reference_id_monday"])
        empty_summary = pd.DataFrame(columns=["reference_id_monday", "qtd_duplicados"])
        return empty_duplicates, empty_summary

    df_monday_valid = df_monday_all_items.copy()
    df_monday_valid["reference_id_monday"] = df_monday_valid["reference_id_monday"].astype("string")
    df_monday_valid = df_monday_valid.dropna(subset=["reference_id_monday"]).copy()

    df_monday_duplicates = (
        df_monday_valid[
            df_monday_valid.duplicated(subset=["reference_id_monday"], keep=False)
        ]
        .sort_values(["reference_id_monday", "item_id"])
        .reset_index(drop=True)
    )

    df_duplicate_summary = (
        df_monday_duplicates
        .groupby("reference_id_monday", as_index=False)
        .size()
        .rename(columns={"size": "qtd_duplicados"})
        .sort_values(["qtd_duplicados", "reference_id_monday"], ascending=[False, True])
        .reset_index(drop=True)
    )

    return df_monday_duplicates, df_duplicate_summary


def build_duplicate_resolution(
    df_monday_duplicates: pd.DataFrame,
    df_duplicate_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, list[int]]:
    """
    Decide qual item manter e quais deletar entre duplicados.

    Regra atual:
    - manter o menor item_id por reference_id_monday
    - deletar todos os demais

    Args:
        df_monday_duplicates:
            DataFrame com colunas:
            - item_id
            - reference_id_monday

        df_duplicate_summary:
            DataFrame com colunas:
            - reference_id_monday
            - qtd_duplicados

    Returns:
        df_duplicate_resolution:
            DataFrame consolidado com:
            - reference_id_monday
            - qtd_duplicados
            - item_id_keep
            - item_id_delete

        item_ids_to_delete:
            Lista de item_id que devem ser deletados
    """
    if df_monday_duplicates is None or df_monday_duplicates.empty:
        empty_resolution = pd.DataFrame(
            columns=["reference_id_monday", "qtd_duplicados", "item_id_keep", "item_id_delete"]
        )
        return empty_resolution, []

    df_duplicates_base = df_monday_duplicates.copy()
    df_duplicates_base["item_id"] = df_duplicates_base["item_id"].astype("int64")
    df_duplicates_base["reference_id_monday"] = df_duplicates_base["reference_id_monday"].astype("string")

    df_items_to_keep = (
        df_duplicates_base
        .sort_values(["reference_id_monday", "item_id"])
        .groupby("reference_id_monday", as_index=False)
        .first()[["reference_id_monday", "item_id"]]
        .rename(columns={"item_id": "item_id_keep"})
    )

    df_duplicates_marked = df_duplicates_base.merge(
        df_items_to_keep,
        on="reference_id_monday",
        how="left",
    )

    df_items_to_delete = (
        df_duplicates_marked[
            df_duplicates_marked["item_id"] != df_duplicates_marked["item_id_keep"]
        ][["reference_id_monday", "item_id", "item_id_keep"]]
        .rename(columns={"item_id": "item_id_delete"})
        .reset_index(drop=True)
    )

    df_duplicate_resolution = (
        df_items_to_delete
        .merge(df_duplicate_summary, on="reference_id_monday", how="left")
        [["reference_id_monday", "qtd_duplicados", "item_id_keep", "item_id_delete"]]
        .sort_values(["qtd_duplicados", "reference_id_monday", "item_id_delete"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    item_ids_to_delete = df_duplicate_resolution["item_id_delete"].tolist()

    return df_duplicate_resolution, item_ids_to_delete


if __name__ == "__main__":
    df_monday_all_items_example = pd.DataFrame(
        {
            "item_id": [1, 2, 3, 4, 5, 6],
            "reference_id_monday": [
                "SPT 111 - 2026-02-24",
                "SPT 111 - 2026-02-24",
                "SPT 151 - 2026-02-24",
                "SPT 151 - 2026-02-24",
                "SPT 60 - 2026-02-24",
                "SPT 60 - 2026-02-24",
            ],
        }
    )

    df_monday_duplicates, df_duplicate_summary = find_monday_duplicates(df_monday_all_items_example)

    df_duplicate_resolution, item_ids_to_delete = build_duplicate_resolution(
        df_monday_duplicates=df_monday_duplicates,
        df_duplicate_summary=df_duplicate_summary,
    )

    print(df_duplicate_summary)
    print(df_duplicate_resolution)
    print("item_ids_to_delete:", item_ids_to_delete)