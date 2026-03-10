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

QUERY_ITEMS_ALL = """
query ($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items { id name group { id } }
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
    request_headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }
    request_payload = {
        "query": query,
        "variables": variables,
    }

    for attempt in range(retries + 1):
        try:
            response = session.post(
                MONDAY_BASE_URL,
                json=request_payload,
                headers=request_headers,
                timeout=timeout_s,
            )

            if response.status_code == 429:
                wait_seconds = float(
                    response.headers.get(
                        "Retry-After",
                        min(backoff_cap, backoff_base * (2 ** attempt)),
                    )
                )
                time.sleep(wait_seconds + random.random() * 0.25)
                continue

            if response.status_code >= 500:
                wait_seconds = min(backoff_cap, backoff_base * (2 ** attempt))
                time.sleep(wait_seconds + random.random() * 0.25)
                continue

            response.raise_for_status()

            response_payload = response.json()
            if response_payload.get("errors"):
                raise RuntimeError(response_payload["errors"])

            return response_payload

        except (requests.Timeout, requests.ConnectionError):
            if attempt == retries:
                raise
            wait_seconds = min(backoff_cap, backoff_base * (2 ** attempt))
            time.sleep(wait_seconds + random.random() * 0.25)

    raise RuntimeError("Falha inesperada ao consultar Monday.")


def fetch_monday_all_items(limit: int = 500) -> pd.DataFrame:
    """
    Busca TODOS os itens do board no Monday, incluindo duplicados.

    Retorna DataFrame com:
    - item_id
    - reference_id_monday
    """
    if not MONDAY_API_TOKEN:
        raise RuntimeError("MONDAY_API_TOKEN não definido no .env")
    if not MONDAY_BOARD_ID:
        raise RuntimeError("MONDAY_BOARD_ID não definido no .env")

    collected_rows: list[dict] = []

    with requests.Session() as session:
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
            raise RuntimeError(
                f"Resposta inesperada do Monday ao buscar items_count: {count_payload}"
            ) from exc

        total_pages = math.ceil(total_items / limit) if total_items else 0
        cursor = None

        with tqdm(total=total_pages, desc="Lendo Monday", unit="page") as progress_bar:
            while True:
                page_payload = monday_post(
                    session=session,
                    query=QUERY_ITEMS_ALL,
                    variables={
                        "board_id": str(MONDAY_BOARD_ID),
                        "limit": int(limit),
                        "cursor": cursor,
                    },
                    token=MONDAY_API_TOKEN,
                    retries=MONDAY_MAX_RETRIES,
                    backoff_base=MONDAY_BACKOFF_BASE,
                    backoff_cap=MONDAY_BACKOFF_CAP,
                    timeout_s=MONDAY_TIMEOUT_S,
                )

                try:
                    items_page = page_payload["data"]["boards"][0]["items_page"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError(
                        f"Resposta inesperada do Monday ao buscar items_page: {page_payload}"
                    ) from exc

                monday_items = items_page.get("items", [])

                for monday_item in monday_items:
                    collected_rows.append(
                        {
                            "item_id": monday_item.get("id"),
                            "reference_id_monday": monday_item.get("name"),
                            "group_id": (monday_item.get("group") or {}).get("id"),
                        }
                    )

                progress_bar.update(1)
                progress_bar.set_postfix(lidos=len(collected_rows), total=total_items)

                cursor = items_page.get("cursor")
                if not cursor:
                    break

    df_monday_all_items = pd.DataFrame(
        collected_rows,
        columns=["item_id", "reference_id_monday", "group_id"],
    )

    return df_monday_all_items


if __name__ == "__main__":
    df_monday_all_items = fetch_monday_all_items(limit=500)
    print(df_monday_all_items)