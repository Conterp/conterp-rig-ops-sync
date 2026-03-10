from __future__ import annotations

import sys
import json

from src.config.settings import MONDAY_GROUP_EFICIENCIA
from src.config.settings import MONDAY_GROUP_FALTANTES

from src.config.settings import check_required_envs
from src.core.monday.fetch_monday_ids import fetch_monday_ids
from src.core.rig.auth import get_rig_token, build_rig_session
from src.core.rig.fetch_rigs import fetch_rigs, rigs_to_records
from src.utils.fetch_current_date import print_date_range_from_start
from src.core.rig.fetch_reference_ids import fetch_reference_ids
from src.utils.find_missing_reference_ids import find_missing_reference_ids
from src.utils.find_new_reference_ids import find_new_reference_ids
from src.utils.build_rig_date_ranges import build_rig_date_ranges
from src.core.rig.fetch_enrich_by_ranges import fetch_enrich_by_ranges
from src.core.monday.build_monday_payloads import build_monday_payloads
from src.core.monday.create_monday_items import create_monday_items
from src.core.monday.fetch_monday_all_items import fetch_monday_all_items
from src.core.monday.build_missing_payloads import build_missing_payloads
from src.core.monday.find_duplicate_items import (
    find_monday_duplicates,
    build_duplicate_resolution,
)
from src.core.monday.delete_monday_items import delete_monday_items
from src.core.monday.find_orphan_items import find_monday_orphans

def main() -> int:
    print("---------------------------------")
    print("\n🚀 Iniciando RIG PIPELINE...\n")
    print("---------------------------------")

    # 1) Checking variáveis de ambiente .env
    print("\n")
    print("1) Validando variáveis de ambiente...")
    check_required_envs()

    # 2) Busca Todos ID's do Grupo Eficiência Monday
    print("\n")
    print("\n2) Lendo itens do Monday e filtrando IDs do grupo 'Eficiência'...")

    df_monday_all_items_efficiency = fetch_monday_all_items(limit=500)

    if "group_id" not in df_monday_all_items_efficiency.columns:
        raise RuntimeError(
            "fetch_monday_all_items não retornou 'group_id'. Verifique fetch_monday_all_items.py"
        )

    df_monday_eff_ids = df_monday_all_items_efficiency[
        df_monday_all_items_efficiency["group_id"] == MONDAY_GROUP_EFICIENCIA
    ].copy()

    df_monday_ids = df_monday_eff_ids.rename(columns={"reference_id_monday": "Monday ID"})[["Monday ID"]]

    print(f"Total IDs em Eficiência: {len(df_monday_ids)}")
    print(df_monday_ids)

    # 3) Autenticação no RigMgt
    print("\n")
    print("\n3) Autenticando no RigMgt...")
    rig_token = get_rig_token()
    print(f"✅ Token RigMgt gerado ({rig_token[:20]}...)")

    # 4) Buscando id das Sondas no Rig
    print("\n")
    print("\n4) Buscando ID's das Sondas no Rig...")
    rig_session = build_rig_session(rig_token)
    df_rigs_ids = fetch_rigs(session=rig_session)
    print(df_rigs_ids)
    print(f"{len(df_rigs_ids)} rows × {df_rigs_ids.shape[1]} columns")

    # 5) Definindo datas para Query Params
    print("\n")
    print("\n5) Definindo Data Atual...")
    START_DATE, END_DATE = print_date_range_from_start()
    print("START_DATE:", START_DATE)
    print("END_DATE:", END_DATE)
    
    # 6) Criando reference_id para comparar com id no Monday
    print("\n")
    print("\n6) Criando reference_id pelo RigMgt...")
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

    # 7) Descobrindo registros faltantes
    print("\n")
    print("\n7) Descobrindo registros faltantes (sonda x data)...")

    df_missing = find_missing_reference_ids(
        df_rigs=df_rigs_ids,      
        df_base=df_base,   
        start_date=START_DATE,
        end_date=END_DATE,
    )

    print(df_missing)
    print("Total Faltantes:", len(df_missing))

    # 8) Descobrindo novos reference_ids
    print("\n")
    print("\n8) Descobrindo Novos reference_ids para Eficiência...")
    df_new_ids = find_new_reference_ids(
        df_monday_ids_existing=df_monday_ids,
        df_base=df_base,
    )
    print(df_new_ids)

    # 9) Criando ranges de datas para enriquecimento
    print("\n")
    print("\n9) Criando ranges de datas...")
    df_ranges = build_rig_date_ranges(df_new_ids)

    print(df_ranges)
    print(f"Qtd ranges: {len(df_ranges)}")
    print(f"Total dias: {int(df_ranges['days'].sum())}")

    # 10) Enriquecendo dados por range
    print("\n")
    print("\n10) Enriquecendo dados por range...")
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

    # 11) Preparando payloads para Monday
    print("\n")
    print("\n11) Preparando payloads para o Monday...")
    monday_payloads = build_monday_payloads(df_rig_operational_daily_valid)

    print(f"Total para subir (Eficiência): {len(monday_payloads)}")
    if monday_payloads:
        print(json.dumps(monday_payloads[0], indent=2))
        
    # 12) Subindo Novos Registros em 'Eficiência' no Monday
    print("\n")
    print("\n12) Subindo Novos Registros em 'Eficiência' no Monday")
    successful_creations, failed_creations = create_monday_items(monday_payloads)

    print(f"✅ Sucessos: {len(successful_creations)}")
    print(f"❌ Falhas: {len(failed_creations)}")
    if failed_creations:
        print("Exemplo de falha:", failed_creations[0])


    # 13) Recarregando itens do Monday
    print("\n")
    print("\n13)🔄 Recarregando todos os itens do Monday...")
    df_monday_all_items = fetch_monday_all_items(limit=500)
    print(df_monday_all_items)
    
    # 14) Filtrando registros faltantes (evitar subir repetido no grupo Faltantes)
    print("\n")
    print("\n14)🧪 Filtrando Registros Faltantes")

    if "group_id" not in df_monday_all_items.columns:
        raise RuntimeError(
            "df_monday_all_items não possui coluna 'group_id'. "
            "Confirme se fetch_monday_all_items.py está retornando group_id."
        )

    df_monday_faltantes = df_monday_all_items[
        df_monday_all_items["group_id"] == MONDAY_GROUP_FALTANTES
    ].copy()

    existing_missing_ids = set(
        df_monday_faltantes["reference_id_monday"].dropna().astype("string")
    )

    print(f"Itens Faltantes já no Monday: {len(existing_missing_ids)}")

    # 14.1) Deletando Órfãos de Datas Faltantes
    print("\n")
    print("\n14.1) 🗑️ Deletando Órfãos de Datas Faltantes")

    expected_missing_ids = set(df_missing["reference_id"].dropna().astype("string")) if df_missing is not None else set()
    current_missing_ids = set(df_monday_faltantes["reference_id_monday"].dropna().astype("string"))

    ids_to_delete_noise = current_missing_ids - expected_missing_ids

    df_noise = df_monday_faltantes[
        df_monday_faltantes["reference_id_monday"].astype("string").isin(ids_to_delete_noise)
    ].copy()

    item_ids_to_delete_noise = df_noise["item_id"].astype("int64").tolist()

    print(f"Itens 'lixo' a deletar em Datas Faltantes: {len(item_ids_to_delete_noise)}")
    print("Exemplo ids:", item_ids_to_delete_noise[:10])

    successful_noise_del, failed_noise_del = delete_monday_items(
        item_ids_to_delete=item_ids_to_delete_noise,
        progress_description="🧹 Limpando Datas Faltantes (lixo/manual)",
        dry_run=False,
    )

    print(f"✅ Limpados (Faltantes): {len(successful_noise_del)}")
    print(f"❌ Falhas ao limpar (Faltantes): {len(failed_noise_del)}")
    if failed_noise_del:
        print("Exemplo de falha:", failed_noise_del[0])

    existing_missing_ids = current_missing_ids.intersection(expected_missing_ids)
    
    if df_missing is None or df_missing.empty:
        df_missing_to_create = df_missing
    else:
        df_missing_to_create = df_missing[
            ~df_missing["reference_id"].astype("string").isin(existing_missing_ids)
        ].copy()

    print(f"Faltantes NOVOS para criar (pós-limpeza): {0 if df_missing_to_create is None else len(df_missing_to_create)}")
    if df_missing_to_create is not None and not df_missing_to_create.empty:
        print(df_missing_to_create)
    print(f"Itens válidos que permanecem em Datas Faltantes: {len(existing_missing_ids)}")

    # 15) Criando itens no Grupo 'Datas Faltantes'
    print("\n")
    print("\n15)💾 Criando itens no grupo 'Datas Faltantes'...")

    missing_payloads = build_missing_payloads(df_missing_to_create)

    print(f"Total faltantes para criar: {len(missing_payloads)}")
    if missing_payloads:
        print(json.dumps(missing_payloads[0], indent=2, ensure_ascii=False))

    successful_missing, failed_missing = create_monday_items(missing_payloads)

    print(f"✅ Faltantes criados: {len(successful_missing)}")
    print(f"❌ Falhas ao criar faltantes: {len(failed_missing)}")
    if failed_missing:
        print("Exemplo de falha:", failed_missing[0])
        
    # 16) Removendo do grupo 'Datas Faltantes' os itens que já viraram válidos na API
    print("\n")
    print("\n16)🗑️ Removendo de “Datas Faltantes” os Registros que Agora têm Dados Válidos")

    valid_rig_ids = set(df_rig_reference_id["reference_id"].dropna().astype("string"))

    df_faltantes_to_remove = df_monday_faltantes[
        df_monday_faltantes["reference_id_monday"].astype("string").isin(valid_rig_ids)
    ].copy()

    item_ids_to_remove_from_faltantes = df_faltantes_to_remove["item_id"].astype("int64").tolist()

    print(f"Itens a remover do grupo Faltantes (viraram válidos): {len(item_ids_to_remove_from_faltantes)}")
    print("Exemplo ids a remover:", item_ids_to_remove_from_faltantes[:10])

    successful_rm_faltantes, failed_rm_faltantes = delete_monday_items(
        item_ids_to_delete=item_ids_to_remove_from_faltantes,
        progress_description="🗑️ Limpando Faltantes (viraram válidos)",
        dry_run=False,
    )

    print(f"✅ Removidos do Faltantes: {len(successful_rm_faltantes)}")
    print(f"❌ Falhas ao remover do Faltantes: {len(failed_rm_faltantes)}")
    if failed_rm_faltantes:
        print("Exemplo de falha:", failed_rm_faltantes[0])
        
    # 16.1) Recarregando Monday após limpeza do grupo Faltantes...
    print("\n")
    print("\n16.1)⏳ Recarregando Monday após limpeza do grupo Faltantes...")
    df_monday_all_items = fetch_monday_all_items(limit=500)
        
        
    # 17) Encontrando Duplicados de 'Eficiência' no Monday
    print("\n")
    print("\n17)👯 Encontrando Duplicados de 'Eficiência' no Monday...")
    df_monday_eff = df_monday_all_items[df_monday_all_items["group_id"] == MONDAY_GROUP_EFICIENCIA].copy()
    
    df_monday_duplicates, df_duplicate_summary = find_monday_duplicates(df_monday_eff)

    df_duplicate_resolution, item_ids_to_delete = build_duplicate_resolution(
        df_monday_duplicates=df_monday_duplicates,
        df_duplicate_summary=df_duplicate_summary,
    )

    print(f"\n {df_duplicate_summary}")
    print(f"\n {df_duplicate_resolution}")
    print("Itens a deletar:", len(item_ids_to_delete))
    print("Exemplo ids a deletar:", item_ids_to_delete[:2])


    # 18) Deletando duplicados de 'Eficiência' no Monday
    print("\n")
    print("\n18) Deletando duplicados de 'Eficiência' no Monday...")
    successful_deletions, failed_deletions = delete_monday_items(
        item_ids_to_delete=item_ids_to_delete,
        progress_description="🗑️ Deletando duplicados",
        dry_run=False,  # coloque True se quiser simular
    )

    print(f"✅ Deletados: {len(successful_deletions)}")
    print(f"❌ Falhas: {len(failed_deletions)}")
    if failed_deletions:
        print("Exemplo de falha:", failed_deletions[0])
        
    # 18.1) Encontrando e deletando duplicados no grupo 'Datas Faltantes'...
    print("\n")
    print("\n18.1) Deletando Duplicados 'Datas Faltantes' no Monday...")

    df_monday_faltantes_now = df_monday_all_items[df_monday_all_items["group_id"] == MONDAY_GROUP_FALTANTES].copy()

    df_dup_falt, df_sum_falt = find_monday_duplicates(df_monday_faltantes_now)
    df_res_falt, ids_del_falt = build_duplicate_resolution(df_dup_falt, df_sum_falt)

    print("Duplicados em Faltantes:", len(ids_del_falt))
    print("Exemplo ids:", ids_del_falt[:10])

    successful_del_falt, failed_del_falt = delete_monday_items(
        item_ids_to_delete=ids_del_falt,
        progress_description="🗑️ Deletando duplicados (Faltantes)",
        dry_run=False,
    )

    print(f"✅ Deletados (Faltantes): {len(successful_del_falt)}")
    print(f"❌ Falhas (Faltantes): {len(failed_del_falt)}")


    # 19) Identificando Órfãos de 'Eficiência' no Monday
    print("\n")
    print("\n19) Identificando Órfãos de 'Eficiência' no Monday")
    df_monday_eff = df_monday_all_items[df_monday_all_items["group_id"] == MONDAY_GROUP_EFICIENCIA].copy()
    df_monday_orphans, orphan_item_ids_to_delete = find_monday_orphans(
        df_rig_reference_id=df_rig_reference_id,
        df_monday_all_items=df_monday_eff,
    )

    print(df_monday_orphans)
    print("Órfãos encontrados:", len(df_monday_orphans))
    print("Exemplo ids órfãos a deletar:", orphan_item_ids_to_delete[:2])


    # 20) Deletando Órfãos de Eficiência no Monday
    print("\n")
    print("\n20) Deletando Órfãos de Eficiência no Monday...")
    successful_orphan_deletions, failed_orphan_deletions = delete_monday_items(
        item_ids_to_delete=orphan_item_ids_to_delete,
        progress_description="🗑️ Deletando órfãos",
        dry_run=False,
    )

    print(f"✅ Órfãos deletados: {len(successful_orphan_deletions)}")
    print(f"❌ Falhas ao deletar órfãos: {len(failed_orphan_deletions)}")
    if failed_orphan_deletions:
        print("Exemplo de falha:", failed_orphan_deletions[0])

    print("\n🏁 Pipeline Rig concluído.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())