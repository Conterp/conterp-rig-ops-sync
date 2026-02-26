from __future__ import annotations

import sys

from src.config.settings import check_required_envs
from src.core.rig.auth import get_rig_token


def main() -> int:
    print("\n🚀 Iniciando RIG PIPELINE\n")

    # 1) Checking variáveis de ambiente .env
    print("1️⃣ Validando variáveis de ambiente...")
    check_required_envs()

    # 2) Autenticação no RigMgt
    print("\n2️⃣ Autenticando no RigMgt...")
    token = get_rig_token()
    print(f"✅ RigMgt login OK. Token gerado ({token[:5]}...)")

    print("\n🏁 Pipeline Rig concluído.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())