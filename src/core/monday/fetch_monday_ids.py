import time
import random
import math
import requests
import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    MONDAY_BASE_URL,
    MONDAY_API_TOKEN,
    MONDAY_BOARD_ID,
    MONDAY_TIMEOUT_S,
    MONDAY_MAX_RETRIES,
    MONDAY_BACKOFF_BASE,
    MONDAY_BACKOFF_CAP,
)

QUERY_COUNT = """
query ($board_id: ID!) {
  boards(ids: [$board_id]) { items_count }
}
"""

QUERY_ITEMS = """
query ($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items { name }
    }
  }
}
"""


def monday_post(
    session: requests.Session,
    query: str,
    variables: dict,
    token: str,
    retries: int,
    backoff_base: float,
    backoff_cap: float,
    timeout_s: int,
) -> dict:
    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {"query": query, "variables": variables}

    for attempt in range(retries + 1):
        try:
            response = session.post(
                MONDAY_BASE_URL,
                json=payload,
                headers=headers,
                timeout=timeout_s,
            )

            # Rate limit
            if response.status_code == 429:
                wait = float(
                    response.headers.get(
                        "Retry-After",
                        min(backoff_cap, backoff_base * (2 ** attempt)),
                    )
                )
                time.sleep(wait + random.random() * 0.25)
                continue

            # Erros transitórios
            if response.status_code >= 500:
                wait = min(backoff_cap, backoff_base * (2 ** attempt))
                time.sleep(wait + random.random() * 0.25)
                continue

            response.raise_for_status()

            response_payload = response.json()
            if response_payload.get("errors"):
                raise RuntimeError(response_payload["errors"])

            return response_payload

        except (requests.Timeout, requests.ConnectionError):
            if attempt == retries:
                raise
            wait = min(backoff_cap, backoff_base * (2 ** attempt))
            time.sleep(wait + random.random() * 0.25)


def fetch_existing_ids(limit: int = 500) -> set[str]:
    """
    Lê todos os items do board e retorna um set com os valores de item.name (IDs).
    Usa paginação via cursor e mostra progresso (%), usando items_count.
    """
    if not MONDAY_API_TOKEN:
        raise RuntimeError("MONDAY_API_TOKEN não definido no .env")
    if not MONDAY_BOARD_ID:
        raise RuntimeError("MONDAY_BOARD_ID não definido no .env")

    existing_ids: set[str] = set()

    with requests.Session() as session:
        # Total pra barra em %
        count_payload = monday_post(
            session=session,
            query=QUERY_COUNT,
            variables={"board_id": str(MONDAY_BOARD_ID)},
            token=MONDAY_API_TOKEN,
            retries=MONDAY_MAX_RETRIES,
            backoff_base=MONDAY_BACKOFF_BASE,
            backoff_cap=MONDAY_BACKOFF_CAP,
            timeout_s=MONDAY_TIMEOUT_S,
        )

        try:
            total_items = count_payload["data"]["boards"][0]["items_count"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Resposta inesperada do Monday (items_count): {count_payload}") from exc

        total_pages = math.ceil(total_items / limit) if total_items else 0

        cursor = None
        with tqdm(total=total_pages, desc="Lendo Monday", unit="page") as pbar:
            while True:
                page_payload = monday_post(
                    session=session,
                    query=QUERY_ITEMS,
                    variables={"board_id": str(MONDAY_BOARD_ID), "limit": int(limit), "cursor": cursor},
                    token=MONDAY_API_TOKEN,
                    retries=MONDAY_MAX_RETRIES,
                    backoff_base=MONDAY_BACKOFF_BASE,
                    backoff_cap=MONDAY_BACKOFF_CAP,
                    timeout_s=MONDAY_TIMEOUT_S,
                )

                try:
                    items_page = page_payload["data"]["boards"][0]["items_page"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError(f"Resposta inesperada do Monday (items_page): {page_payload}") from exc

                items = items_page.get("items", [])
                for item in items:
                    item_name = item.get("name")
                    if item_name:
                        existing_ids.add(item_name)

                pbar.update(1)
                pbar.set_postfix(itens=len(existing_ids), total=total_items)

                cursor = items_page.get("cursor")
                if not cursor:
                    break

    return existing_ids


def fetch_monday_ids_df(limit: int = 500) -> pd.DataFrame:
    """
    Retorna um DataFrame com 1 coluna: 'Monday ID'
    (a partir dos item.name do Monday).
    """
    existing_ids = fetch_existing_ids(limit=limit)
    return pd.DataFrame({"Monday ID": list(existing_ids)})


if __name__ == "__main__":
    df_monday_ids_existing = fetch_monday_ids_df(limit=500)
    print(df_monday_ids_existing)
    print(f"{len(df_monday_ids_existing)} rows × {df_monday_ids_existing.shape[1]} columns")