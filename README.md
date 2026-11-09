# rag-observability

Pipeline de RAG **agnóstico de domínio**, **observável** (OpenTelemetry) e **governado**
(allowlist de modelos, orçamento e ledger de uso). Você descreve o seu domínio num YAML,
escolhe provedor de modelos e vector store por variável de ambiente, e o núcleo não muda.

Derivado do projeto open source
[`devfullcycle/mba-ia-rag` (branch `observability`)](https://github.com/devfullcycle/mba-ia-rag/tree/observability),
cujo histórico git está preservado aqui. O que mudou, e por quê, está em
[`docs/design/07-diferencas-upstream.md`](docs/design/07-diferencas-upstream.md) e nos
[ADRs](docs/adr/README.md).

## O que o pipeline faz

```
pergunta ─► política (modelo permitido? orçamento?) ── bloqueado → resposta controlada
             │
             ▼
           query planner ── ambígua? → pergunta de esclarecimento
             │  (reescreve, extrai termos literais, escolhe facetas do profile)
             ▼
           retrieval filtrado (escopo de autorização + facetas) ── nada? → "não encontrei"
             │
             ▼
           reranking ── nada relevante? → "não encontrei" (sem chamar a resposta)
             │
             ▼
           resposta + fontes (só ids que estavam mesmo no contexto)
```

Cada etapa vira um span (`rag.*` + `gen_ai.*`), cada execução uma linha de log JSON e,
se chamou modelo, uma linha no ledger de uso.

## Conceitos

| Peça | Onde | Muda quando… |
| --- | --- | --- |
| **Domain Profile** | `profiles/<nome>/profile.yaml` | muda o assunto: facetas, escopo, idioma, mensagens, chunking |
| **Settings** | `.env` | muda o ambiente: provedor, modelo, vector store, observabilidade, limites |
| **Preços** | `config/pricing.yaml` | muda a tabela do provedor |
| **Núcleo** | `rag_observability/` | muda o método (raramente) |

Dois profiles de exemplo: `fcai-saas-support` (o domínio original do upstream, em
português) e `hr-handbook` (manual de RH em inglês, multi-empresa por escopo de
requisição).

## Início rápido (sem Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # preencha OPENAI_API_KEY

export VECTOR_STORE=memory      # índice em arquivo, zero infraestrutura
python -m rag_observability.ingestion.ingest
python -m rag_observability.ingestion.index
python -m rag_observability.cli.doctor
python -m rag_observability.cli.chat --debug
```

Outro domínio:

```bash
export RAG_PROFILE=profiles/hr-handbook/profile.yaml
python -m rag_observability.ingestion.ingest && python -m rag_observability.ingestion.index
python -m rag_observability.cli.chat --scope company=acme-labs
```

## Com pgvector e observabilidade

```bash
docker compose up -d                              # Postgres + pgvector (porta 5433)
docker compose --profile jaeger up -d             # Jaeger: http://localhost:16686
docker compose --profile observability up -d      # Langfuse: http://localhost:3000 (admin@rag.local / langfuse123)
```

```bash
VECTOR_STORE=pgvector
OBSERVABILITY_ENABLED=true
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318              # Jaeger / Collector
# ou, para o Langfuse local:
LANGFUSE_PUBLIC_KEY=pk-lf-rag-local
LANGFUSE_SECRET_KEY=sk-lf-rag-local
```

## API

```bash
uvicorn rag_observability.api:app --reload
curl -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -d '{"question": "Qual é o SLA para incidentes P1 no plano Enterprise?", "debug": true}'
```

`400` para pergunta vazia, `403` para escopo inválido, `500` genérico em falha,
`200` com `policy_blocked: true` quando a política bloqueia. Exemplos prontos em
`test.http`. Para multi-tenant, injete o seu `ScopeResolver` em `create_app()` (ou use
`API_SCOPE_FROM_HEADERS=true` atrás de um gateway confiável).

## Trocar provedor, store, ledger

```bash
pip install langchain-anthropic
LLM_PROVIDER=anthropic LLM_MODEL=claude-sonnet-4-5 AI_ALLOWED_MODELS=claude-sonnet-4-5

EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=nomic-embed-text   # pip install langchain-ollama

VECTOR_STORE=meu_pacote.qdrant:QdrantIndex
AI_USAGE_LEDGER=meu_pacote.ledger:RedisLedger
```

Detalhes em [`docs/design/06-extensao.md`](docs/design/06-extensao.md).

## Ferramentas

| Comando | Para quê |
| --- | --- |
| `python -m rag_observability.ingestion.ingest` | valida front matter e facetas, gera `data/<collection>/chunks.jsonl` |
| `python -m rag_observability.ingestion.index [--force]` | indexa só o que mudou |
| `python -m rag_observability.cli.chat [--debug] [--show-prompt] [--no-rerank] [--scope k=v]` | chat no terminal |
| `python -m rag_observability.cli.retrieve "pergunta" [--filter k=v]` | só a busca, sem modelo de chat |
| `python -m rag_observability.cli.doctor` | checa configuração, pacotes, store e contrato índice×profile sem gastar tokens |
| `pytest` | suíte offline (fakes de modelo e embeddings) |

## Documentação

- [Design docs](docs/design/README.md) — arquitetura, especificação do profile,
  pipeline, observabilidade, governança, extensão, diferenças do upstream.
- [ADRs](docs/adr/README.md) — as 15 decisões e suas alternativas.

## Licença

O repositório upstream não declara um arquivo de licença. Antes de redistribuir,
confirme os termos com os autores do upstream e adicione aqui a licença aplicável.
