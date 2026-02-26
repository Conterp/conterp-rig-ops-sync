from datetime import datetime
from zoneinfo import ZoneInfo

from src.config.settings import PIPELINE_TZ, PIPELINE_START_DATE


def get_today_iso() -> str:
    """
    Retorna a data de hoje no fuso configurado (PIPELINE_TZ), formato YYYY-MM-DD.
    """
    tz = ZoneInfo(PIPELINE_TZ)
    return datetime.now(tz).date().isoformat()


def get_date_range_from_start() -> tuple[str, str]:
    """
    Retorna (START_DATE, END_DATE) onde:
    - START_DATE vem do .env (PIPELINE_START_DATE)
    - END_DATE é a data de hoje no fuso configurado
    """
    return PIPELINE_START_DATE, get_today_iso()


def print_date_range_from_start() -> tuple[str, str]:
    """
    Igual ao get_date_range_from_start(), mas imprime.
    """
    start_date, end_date = get_date_range_from_start()
    
    return start_date, end_date


if __name__ == "__main__":
    # Teste rápido (rodando o arquivo diretamente)
    start_date, end_date = print_date_range_from_start()
    print("START_DATE:", start_date)
    print("END_DATE:", end_date)