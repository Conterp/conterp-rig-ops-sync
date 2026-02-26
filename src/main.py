from __future__ import annotations

import sys

from src.config.settings import check_required_envs
from src.core.monday.fetch_monday_ids import fetch_monday_ids_df
from src.core.rig.auth import get_rig_token, build_rig_session
from src.core.rig.fetch_rigs import fetch_rigs, rigs_to_records
from src.utils.fetch_current_date import print_date_range_from_start
from src.core.rig.fetch_reference_ids import fetch_reference_ids


def main() -> int:
    print("\n🚀 Iniciando RIG PIPELINE...\n")

    # 1) Checking variáveis de ambiente .env
    print("1️⃣ Validando variáveis de ambiente...")
    check_required_envs()

    # 2) Busca todos ID's que já existem no monday
    print("\n2️⃣ Lendo todos ID's que existem no Monday...")
    df_monday_ids = fetch_monday_ids_df(limit=500)
    print(df_monday_ids)

    # 3) Autenticação no RigMgt
    print("\n3️⃣ Autenticando no RigMgt...")
    rig_token = get_rig_token()
    print(f"✅ Token RigMgt gerado ({rig_token[:20]}...)")

    # 4) Buscando id das Sondas no Rig
    print("\n4️⃣ Buscando ID's das Sondas no Rig...")
    rig_session = build_rig_session(rig_token)
    df_rigs_ids = fetch_rigs(session=rig_session)
    print(df_rigs_ids)
    print(f"{len(df_rigs_ids)} rows × {df_rigs_ids.shape[1]} columns")

    # 5) Definindo datas para Query Params
    print("\n5️⃣ Definindo data atual...")
    START_DATE, END_DATE = print_date_range_from_start()
    print("START_DATE:", START_DATE)
    print("END_DATE:", END_DATE)
    
    # 6) Criando reference_id para comparar com id no Monday
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

    print("\n🏁 Pipeline Rig concluído.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())