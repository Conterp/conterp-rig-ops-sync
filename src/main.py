from __future__ import annotations

import sys
import json

from src.config.settings import check_required_envs
from src.core.monday.fetch_monday_ids import fetch_monday_ids
from src.core.rig.auth import get_rig_token, build_rig_session
from src.core.rig.fetch_rigs import fetch_rigs, rigs_to_records
from src.utils.fetch_current_date import print_date_range_from_start
from src.core.rig.fetch_reference_ids import fetch_reference_ids
from src.utils.find_new_reference_ids import find_new_reference_ids
from src.utils.build_rig_date_ranges import build_rig_date_ranges
from src.core.rig.fetch_enrich_by_ranges import fetch_enrich_by_ranges
from src.core.monday.build_monday_payloads import build_monday_payloads
from src.core.monday.create_monday_items import create_monday_items
from src.core.monday.fetch_monday_all_items import fetch_monday_all_items
from src.core.monday.find_duplicate_items import (
    find_monday_duplicates,
    build_duplicate_resolution,
)
from src.core.monday.delete_monday_items import delete_monday_items

def main() -> int:
    print("---------------------------------")
    print("\n🚀 Iniciando RIG PIPELINE...\n")
    print("---------------------------------")

    # 1) Checking variáveis de ambiente .env
    print("\n")
    print("1️⃣ Validando variáveis de ambiente...")
    check_required_envs()

    # 2) Busca todos ID's que já existem no monday
    print("\n")
    print("\n2️⃣ Lendo todos ID's que existem no Monday...")
    df_monday_ids = fetch_monday_ids(limit=500)
    print(df_monday_ids)

    # 3) Autenticação no RigMgt
    print("\n")
    print("\n3️⃣ Autenticando no RigMgt...")
    rig_token = get_rig_token()
    print(f"✅ Token RigMgt gerado ({rig_token[:20]}...)")

    # 4) Buscando id das Sondas no Rig
    print("\n")
    print("\n4️⃣ Buscando ID's das Sondas no Rig...")
    rig_session = build_rig_session(rig_token)
    df_rigs_ids = fetch_rigs(session=rig_session)
    print(df_rigs_ids)
    print(f"{len(df_rigs_ids)} rows × {df_rigs_ids.shape[1]} columns")

    # 5) Definindo datas para Query Params
    print("\n")
    print("\n5️⃣ Definindo data atual...")
    START_DATE, END_DATE = print_date_range_from_start()
    print("START_DATE:", START_DATE)
    print("END_DATE:", END_DATE)
    
    # 6) Criando reference_id para comparar com id no Monday
    print("\n")
    print("\n6️⃣ Criando reference_id pelo RigMgt...")
    rigs_records = rigs_to_records(df_rigs_ids)

    df_base, df_rig_reference_id = fetch_reference_ids(
        session=rig_session,
        rigs_records=rigs_records,
        start_date=START_DATE,
        end_date=END_DATE,
        show_progress=True,
    )
    print(df_rig_reference_id)
    print(df_base)

    # 7) Descobrindo novos reference_ids
    print("\n")
    print("\n7️⃣ Descobrindo novos reference_ids...")
    df_new_ids = find_new_reference_ids(
        df_monday_ids_existing=df_monday_ids,
        df_base=df_base,
    )
    print(df_new_ids)

    # 8) Criando ranges de datas para enriquecimento
    print("\n")
    print("\n8️⃣ Criando ranges de datas...")
    df_ranges = build_rig_date_ranges(df_new_ids)

    print(df_ranges)
    print(f"Qtd ranges: {len(df_ranges)}")
    print(f"Total dias: {int(df_ranges['days'].sum())}")

    # 9) Enriquecendo dados por range
    print("\n")
    print("\n9️⃣ Enriquecendo dados por range...")
    (
        df_rig_operational_daily,
        df_rig_operational_daily_valid,
        df_rig_operational_daily_errors,
    ) = fetch_enrich_by_ranges (
        session=rig_session,
        df_ranges=df_ranges,
        show_progress=True,
    )
    print(df_rig_operational_daily_valid)
    print(f"Linhas válidas: {len(df_rig_operational_daily_valid)}")
    print(f"Ranges com erro/vazio: {len(df_rig_operational_daily_errors)}")

    # 10) Preparando payloads para Monday
    print("\n")
    print("\n🔟 Preparando payloads para o Monday...")
    monday_payloads = build_monday_payloads(df_rig_operational_daily_valid)

    print(f"Total para subir: {len(monday_payloads)}")
    if monday_payloads:
        print(json.dumps(monday_payloads[0], indent=2))
        
    # 11) Subindo itens no Monday
    print("\n")
    print("\n1️⃣1️⃣ Subindo itens no Monday...")
    successful_creations, failed_creations = create_monday_items(monday_payloads)

    print(f"✅ Sucessos: {len(successful_creations)}")
    print(f"❌ Falhas: {len(failed_creations)}")
    if failed_creations:
        print("Exemplo de falha:", failed_creations[0])


    # 12) Recarregando itens do Monday
    print("\n")
    print("\n1️⃣2️⃣ Recarregando todos os itens do Monday...")
    df_monday_all_items = fetch_monday_all_items(limit=500)
    print(df_monday_all_items)


    # 13) Encontrando Duplicados
    print("\n")
    print("\n1️⃣3️⃣ Encontrando Duplicados...")
    df_monday_duplicates, df_duplicate_summary = find_monday_duplicates(df_monday_all_items)

    df_duplicate_resolution, item_ids_to_delete = build_duplicate_resolution(
        df_monday_duplicates=df_monday_duplicates,
        df_duplicate_summary=df_duplicate_summary,
    )

    print(f"\n {df_duplicate_summary}")
    print(f"\n {df_duplicate_resolution}")
    print("Itens a deletar:", len(item_ids_to_delete))
    print("Exemplo ids a deletar:", item_ids_to_delete[:10])


    # 14) Deletando duplicados no Monday
    print("\n")
    print("\n1️⃣4️⃣ Deletando duplicados no Monday...")
    successful_deletions, failed_deletions = delete_monday_items(
        item_ids_to_delete=item_ids_to_delete,
        progress_description="🗑️ Deletando duplicados",
        dry_run=False,  # coloque True se quiser simular
    )

    print(f"✅ Deletados: {len(successful_deletions)}")
    print(f"❌ Falhas: {len(failed_deletions)}")
    if failed_deletions:
        print("Exemplo de falha:", failed_deletions[0])


    print("\n🏁 Pipeline Rig concluído.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())