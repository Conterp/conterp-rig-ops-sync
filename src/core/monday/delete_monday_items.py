import time
import random
import requests
from tqdm import tqdm

from src.config.settings import (
    MONDAY_BASE_URL,
    MONDAY_API_TOKEN,
    MONDAY_TIMEOUT_S,
    MONDAY_MAX_RETRIES,
    MONDAY_BACKOFF_BASE,
    MONDAY_BACKOFF_CAP,
    MONDAY_SLEEP_BETWEEN,
)

DELETE_ITEM_MUTATION = """
mutation ($item_id: ID!) {
  delete_item(item_id: $item_id) { id }
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
    POST no Monday com retry/backoff para:
    - erro de rede
    - 429
    - 5xx
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


def delete_monday_item(
    session: requests.Session,
    item_id: int | str,
) -> str:
    """
    Deleta um item no Monday e retorna o id deletado.
    """
    if not MONDAY_API_TOKEN:
        raise RuntimeError("MONDAY_API_TOKEN não definido no .env")

    request_headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
    }

    graphql_variables = {
        "item_id": str(item_id),
    }

    request_payload = {
        "query": DELETE_ITEM_MUTATION,
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

    deleted_item_id = response_payload["data"]["delete_item"]["id"]
    return deleted_item_id


def delete_monday_items(
    item_ids_to_delete: list[int] | list[str],
    progress_description: str = "🗑️ Deletando itens no Monday",
    dry_run: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Deleta vários itens no Monday com controle de ritmo.

    Args:
        item_ids_to_delete:
            Lista de item_ids para deletar
        progress_description:
            Texto do tqdm
        dry_run:
            True = não deleta, só simula

    Returns:
        successful_deletions:
            [{"item_id": ..., "deleted_id": ...}] ou dry_run info
        failed_deletions:
            [{"item_id": ..., "error": ...}]
    """
    successful_deletions: list[dict] = []
    failed_deletions: list[dict] = []

    if item_ids_to_delete is None or len(item_ids_to_delete) == 0:
        return successful_deletions, failed_deletions

    with requests.Session() as session:
        for item_id in tqdm(item_ids_to_delete, desc=progress_description, unit="item"):
            if dry_run:
                successful_deletions.append(
                    {
                        "item_id": item_id,
                        "deleted": False,
                        "dry_run": True,
                    }
                )
                continue

            try:
                deleted_item_id = delete_monday_item(
                    session=session,
                    item_id=item_id,
                )
                successful_deletions.append(
                    {
                        "item_id": item_id,
                        "deleted_id": deleted_item_id,
                    }
                )
            except Exception as exc:
                failed_deletions.append(
                    {
                        "item_id": item_id,
                        "error": str(exc),
                    }
                )

            time.sleep(MONDAY_SLEEP_BETWEEN)

    return successful_deletions, failed_deletions


if __name__ == "__main__":
    example_item_ids_to_delete = [123456789]

    successful_deletions, failed_deletions = delete_monday_items(
        item_ids_to_delete=example_item_ids_to_delete,
        progress_description="🗑️ Deletando exemplo",
        dry_run=True,
    )

    print(f"✅ Deletados (ou simulados): {len(successful_deletions)}")
    print(f"❌ Falhas: {len(failed_deletions)}")
    if failed_deletions:
        print("Exemplo de falha:", failed_deletions[0])