import json
import time
import random
import requests
from tqdm import tqdm

from src.config.settings import (
    MONDAY_BASE_URL,
    MONDAY_API_TOKEN,
    MONDAY_BOARD_ID,
    MONDAY_GROUP_EFICIENCIA,
    MONDAY_GROUP_FALTANTES,
    MONDAY_TIMEOUT_S,
    MONDAY_MAX_RETRIES,
    MONDAY_BACKOFF_BASE,
    MONDAY_BACKOFF_CAP,
    MONDAY_SLEEP_BETWEEN,
)

CREATE_ITEM_MUTATION = """
mutation ($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON!) {
  create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) { id }
}
"""


def monday_post_with_retry(
    session: requests.Session,
    request_payload: dict,
    request_headers: dict,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
    timeout_seconds: int,
) -> requests.Response:
    """
    Faz POST para o Monday com retry/backoff para:
    - erros de rede
    - 429 (rate limit)
    - 5xx (erros transitórios)
    """
    for attempt in range(max_retries + 1):
        try:
            response = session.post(
                MONDAY_BASE_URL,
                headers=request_headers,
                json=request_payload,
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            if attempt == max_retries:
                raise RuntimeError(f"Erro de rede ao chamar Monday: {exc}") from exc

            wait_seconds = min(backoff_cap, backoff_base * (2 ** attempt)) + random.uniform(0, 0.25)
            time.sleep(wait_seconds)
            continue

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = (
                float(retry_after)
                if retry_after
                else min(backoff_cap, backoff_base * (2 ** attempt)) + random.uniform(0, 0.25)
            )

            if attempt == max_retries:
                raise RuntimeError(f"Rate limit no Monday após retries. Corpo: {response.text[:300]}")

            time.sleep(wait_seconds)
            continue

        if 500 <= response.status_code < 600:
            if attempt == max_retries:
                raise RuntimeError(f"Erro {response.status_code} no Monday após retries. Corpo: {response.text[:300]}")

            wait_seconds = min(backoff_cap, backoff_base * (2 ** attempt)) + random.uniform(0, 0.25)
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError("Falhou após retries no Monday.")


def create_monday_item(
    session: requests.Session,
    item_name: str,
    column_values: dict,
    group_id: str,
) -> str:
    """
    Cria um único item no Monday e retorna o item_id criado.
    """
    if not MONDAY_API_TOKEN:
        raise RuntimeError("MONDAY_API_TOKEN não definido no .env")
    if not MONDAY_BOARD_ID:
        raise RuntimeError("MONDAY_BOARD_ID não definido no .env")
    if not group_id:
        raise RuntimeError("group_id vazio/ausente (verifique MONDAY_GROUP_EFICIENCIA/FALTANTES ou payload)")

    request_headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
    }

    graphql_variables = {
        "board_id": str(MONDAY_BOARD_ID),
        "group_id": str(group_id),
        "item_name": item_name,
        "column_values": json.dumps(column_values, ensure_ascii=False),
    }

    request_payload = {
        "query": CREATE_ITEM_MUTATION,
        "variables": graphql_variables,
    }

    response = monday_post_with_retry(
        session=session,
        request_payload=request_payload,
        request_headers=request_headers,
        max_retries=MONDAY_MAX_RETRIES,
        backoff_base=MONDAY_BACKOFF_BASE,
        backoff_cap=MONDAY_BACKOFF_CAP,
        timeout_seconds=MONDAY_TIMEOUT_S,
    )

    response_payload = response.json()

    if response_payload.get("errors"):
        raise RuntimeError(response_payload["errors"])

    created_item_id = response_payload["data"]["create_item"]["id"]
    return created_item_id


def create_monday_items(monday_payloads: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Sobe todos os payloads para o Monday.

    Args:
        monday_payloads:
            Lista no formato:
            [
              {"item_name": "...", "column_values": {...}, "group_id": "..."},
              ...
            ]

    Returns:
        successful_creations:
            [{"item_name": "...", "item_id": "..."}]
        failed_creations:
            [{"item_name": "...", "error": "...", "payload": {...}}]
    """
    successful_creations: list[dict] = []
    failed_creations: list[dict] = []

    if monday_payloads is None or len(monday_payloads) == 0:
        return successful_creations, failed_creations

    if not MONDAY_GROUP_EFICIENCIA:
        raise RuntimeError("MONDAY_GROUP_EFICIENCIA não definido no .env")

    with requests.Session() as session:
        for monday_payload in tqdm(monday_payloads, desc="⬆️ Subindo no Monday", unit="item"):
            item_name = monday_payload["item_name"]
            column_values = monday_payload["column_values"]

            # group_id por item (se não vier, cai no grupo padrão Eficiência)
            group_id = monday_payload.get("group_id") or MONDAY_GROUP_EFICIENCIA

            try:
                created_item_id = create_monday_item(
                    session=session,
                    item_name=item_name,
                    column_values=column_values,
                    group_id=group_id,
                )
                successful_creations.append(
                    {
                        "item_name": item_name,
                        "item_id": created_item_id,
                    }
                )
            except Exception as exc:
                failed_creations.append(
                    {
                        "item_name": item_name,
                        "error": str(exc),
                        "payload": monday_payload,
                    }
                )

            time.sleep(MONDAY_SLEEP_BETWEEN)

    return successful_creations, failed_creations


if __name__ == "__main__":
    # exemplo: cai no grupo padrão (Eficiência) porque não passamos group_id
    example_payloads = [
        {
            "item_name": "teste - SPT 111 - 2026-02-25",
            "column_values": {
                "date4": {"date": "2026-02-25"},
                "color_mky2w7qv": {"label": "SPT 111"},
                "numeric_mky2dcym": 100.0,
            },
            # "group_id": MONDAY_GROUP_FALTANTES,  # descomente pra testar no grupo faltantes
        }
    ]

    successful_creations, failed_creations = create_monday_items(example_payloads)

    print(f"✅ Sucessos: {len(successful_creations)}")
    print(f"❌ Falhas: {len(failed_creations)}")
    if failed_creations:
        print("Exemplo de falha:", failed_creations[0])