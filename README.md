# 🛢️ Conterp Rig Ops Sync

> Integração automatizada entre **RigMgt** e **Monday.com** para sincronizar dados operacionais diários das sondas, com criação de novos registros, deduplicação e limpeza automática.

---

## 🚀 Visão geral

O **Conterp Rig Ops Sync** conecta a API do **RigMgt** ao **Monday.com** para manter atualizado o board com os dados operacionais diários de cada sonda.

A automação:

- autentica no **RigMgt**
- busca as **sondas cadastradas**
- consulta os dados operacionais por período
- gera um **`reference_id` único por sonda/dia**
- garante que **todo registro válido da API** exista no grupo **Eficiência**
- calcula **registros faltantes** (sonda x dia sem dado na API) e mantém no grupo **Datas Faltantes**
- remove **duplicados** (Eficiência e Datas Faltantes)
- remove **itens órfãos** (somente em Eficiência)
- remove **lixo/manual** do grupo Datas Faltantes (ex.: “New item”, “(copy)”, etc.)

O pipeline trata o **RigMgt como fonte da verdade** e o **Monday como destino operacional**.

---

## 🧠 Principais recursos

- 🔄 **Sincronização automática** de dados do **RigMgt** para o **Monday**
- ✅ **Idempotência prática**: múltiplas execuções não devem recriar itens já existentes
- 🧩 **Geração de `reference_id` único** por sonda e data
- 📦 **Enriquecimento dos dados por faixa de datas** (ranges)
- 🧹 **Deduplicação automática** no Monday (Eficiência e Datas Faltantes)
- 🗑️ **Limpeza de itens órfãos** (apenas em Eficiência)
- 🧼 **Limpeza de itens inválidos/manuais** em Datas Faltantes (mantém apenas o que o pipeline identificou)
- 🏷️ **Coluna “Status Sonda”** derivada das horas do dia (regras abaixo)
- ⏱️ **Retry/backoff automático** para chamadas HTTP no RigMgt e Monday
- 📊 **Acompanhamento de progresso** com `tqdm`
- 🐳 **Execução containerizada com Docker**
- 🌬️ **Orquestração via Airflow**

---

## 🧠 Regra de identificação dos registros

A chave lógica usada no pipeline é o **`reference_id`**, montado neste formato:

```text
Nome da Sonda - YYYY-MM-DD
```

Exemplo:

```text
SPT 111 - 2026-02-24
```

Esse valor é usado como referência principal para:

- comparar RigMgt x Monday
- identificar novos registros
- identificar faltantes
- encontrar duplicados
- encontrar órfãos

No **Monday**, o `reference_id` é salvo no **nome do item** (`item.name`).

---

## 🗂️ Grupos no Monday

O pipeline trabalha com **2 grupos** no mesmo board:

- **Eficiência** (`MONDAY_GROUP_EFICIENCIA`): recebe **somente registros válidos** (existem na API)
- **Datas Faltantes** (`MONDAY_GROUP_FALTANTES`): lista **sonda x data** sem registro na API

Regras principais:

- Se um `reference_id` **passar a existir na API**, ele deve ficar em **Eficiência** e ser removido de **Datas Faltantes**
- O grupo **Datas Faltantes** é “controlado pelo pipeline”: itens fora do que o pipeline identificou (ex.: inserções manuais) são removidos

---

## 🏷️ Regra da coluna “Status Sonda”

O pipeline preenche a coluna **Status Sonda** com base nas horas do dia:

- **Parada Programada**: `Parada Programada (Horas) > 0`
- **Sem Contrato**: `Parada Comercial (Horas) > 0`
- **Operando**: `Eficiência (%) > 0`

> Observação: a ordem acima é importante (Parada Programada e Parada Comercial têm prioridade).

---

## 📅 Janela de datas do pipeline

A automação trabalha com um intervalo de datas definido assim:

- **START_DATE**: vem da variável `PIPELINE_START_DATE`
- **END_DATE**: é a data atual no fuso configurado em `PIPELINE_TZ`

Exemplo:

```env
PIPELINE_TZ=America/Sao_Paulo
PIPELINE_START_DATE=2024-01-01
```

---

## 📦 Enriquecimento por ranges

Depois de descobrir quais `reference_id` ainda não existem no grupo **Eficiência** no Monday, o pipeline agrupa essas datas por sonda em **ranges consecutivos**.

### Regras dos ranges

- datas consecutivas viram um **range natural**
- cada range natural é quebrado em blocos de até **`MAX_DIAS_POR_RANGE`**
- isso reduz a quantidade de chamadas e organiza melhor o enriquecimento

Exemplo:

```env
MAX_DIAS_POR_RANGE=10
```

Endpoint usado:

```text
/dashboard/rig/operational-summary
```

---

## 📊 Dados enviados ao Monday (Eficiência)

Os campos mapeados incluem:

- **Data**
- **Sonda**
- **Eficiência (%)**
- **Horas Produtivas**
- **Operação (Horas)**
- **DTM (Horas)**
- **Gloss (Horas)**
- **Reparo (Horas)**
- **Outros (Horas)**
- **Stand By (Horas)**
- **Parada Comercial (Horas)**
- **Parada Programada (Horas)**
- **Status Sonda**

O mapeamento das colunas do Monday é configurado via:

```env
MONDAY_COLS_JSON={...}
```

---

## 🧹 Deduplicação

Após as operações, o pipeline identifica duplicados com base em:

```text
reference_id_monday
```

### Regra de resolução

Quando existem itens duplicados com o mesmo `reference_id`:

- o pipeline **mantém o menor `item_id`**
- e **deleta os demais**

> A deduplicação roda **separadamente** para Eficiência e Datas Faltantes.

---

## 🗑️ Limpeza de órfãos (somente Eficiência)

Um item é considerado órfão quando:

- existe no grupo **Eficiência** no Monday
- mas seu `reference_id_monday` **não existe** na lista de `reference_id` válidos retornados pela API do RigMgt

Esses itens são identificados e excluídos automaticamente.

---

## 🧩 Estrutura do projeto

### Itens na raiz do repositório

```bash
conterp-rig-ops-sync/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── src/
```

### Estrutura principal do `src/`

```bash
src/
├── config/
│   └── settings.py
├── core/
│   ├── monday/
│   │   ├── build_monday_payloads.py
│   │   ├── build_missing_payloads.py
│   │   ├── create_monday_items.py
│   │   ├── delete_monday_items.py
│   │   ├── fetch_monday_all_items.py
│   │   ├── fetch_monday_ids.py
│   │   ├── find_duplicate_items.py
│   │   └── find_orphan_items.py
│   ├── rig/
│   │   ├── auth.py
│   │   ├── fetch_enrich_by_ranges.py
│   │   ├── fetch_reference_ids.py
│   │   └── fetch_rigs.py
│   └── main.py
└── utils/
    ├── build_rig_date_ranges.py
    ├── fetch_current_date.py
    ├── find_new_reference_ids.py
    └── find_missing_reference_ids.py
```

---

## ⚙️ Configuração

### 1) Clone o repositório

```bash
git clone git@github.com:Conterp/conterp-rig-ops-sync.git
cd conterp-rig-ops-sync
```

### 2) Configure o `.env`

Copie o exemplo:

```bash
cp .env.example .env
```

Preencha com os dados da integração:

```env
# ===========================
# RigMgt
# ===========================
RIG_BASE_URL=https://api.abc.com.br
RIG_EMAIL=SEU_EMAIL_AQUI
RIG_PASSWORD=SUA_SENHA_AQUI
RIG_TIMEOUT_S=30

# Retry/backoff (Rig)
RIG_MAX_RETRIES=5
RIG_BACKOFF_BASE=0.8
RIG_BACKOFF_CAP=20

# ===========================
# Monday
# ===========================
MONDAY_BASE_URL=https://api.monday.com/v2
MONDAY_API_TOKEN=SEU_TOKEN_MONDAY_AQUI
MONDAY_TIMEOUT_S=40

# Retry/backoff (Monday)
MONDAY_MAX_RETRIES=8
MONDAY_BACKOFF_BASE=1.0
MONDAY_BACKOFF_CAP=60
MONDAY_SLEEP_BETWEEN=0.35

# Board / Groups
MONDAY_BOARD_ID=1223334444
MONDAY_GROUP_EFICIENCIA=topics
MONDAY_GROUP_FALTANTES=group_xxxxxxxx

# Colunas do board
MONDAY_COLS_JSON={}

# ===========================
# Pipeline
# ===========================
PIPELINE_TZ=America/Sao_Paulo
PIPELINE_START_DATE=2024-01-01
MAX_DIAS_POR_RANGE=10
```

> 💡 O `.env` não deve ser versionado no Git.

---

## 🧭 Execução

### 🔹 Local

```bash
python -m src.main
```

### 🔹 Com Docker Compose

```bash
docker compose up --build
```

---

## 🐳 Docker

O projeto roda em uma imagem baseada em:

```text
python:3.12-slim
```

A imagem:

- instala as dependências do `requirements.txt`
- configura timezone `America/Sao_Paulo`
- copia o projeto
- executa o pipeline com:

```bash
python -u -m src.main
```

---

## 🌬️ Orquestração com Airflow

Em produção, a automação é executada via **Airflow**.

### DAG

- **dag_id**: `rig_ops_sync`
- **timezone**: `America/Sao_Paulo`
- **schedule**: `0 3,15 * * *`
- **catchup**: `False`

### Frequência

A DAG executa:

- **03:00**
- **15:00**

todos os dias.

### Execução

A task principal roda um container Docker com o pipeline:

```bash
docker run --rm   --env-file /opt/automations/conterp-rig-ops-sync/.env   conterp-rig-ops-sync-app
```

---

## 🔒 Segurança e confiabilidade

- credenciais isoladas em `.env`
- autenticação no **RigMgt** e no **Monday**
- retry/backoff para falhas transitórias e rate limit
- execução containerizada
- limpeza automática de inconsistências no board
- sincronização orientada por `reference_id`

---

## 📦 Dependências

Principais bibliotecas usadas no projeto:

```text
requests
urllib3
pandas
tqdm
python-dotenv
```

---

## 🤝 Autor

**João Carser**  
📧 [joaocarser@gmail.com](mailto:joaocarser@gmail.com)  
🌐 [github.com/JoaoCarser](https://github.com/JoaoCarser)
