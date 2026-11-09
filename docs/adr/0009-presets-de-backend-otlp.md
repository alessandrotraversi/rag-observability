# 0009. Backends OTLP como presets; Langfuse deixa de ser caso especial

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream acerta ao não usar SDK de backend: só OTLP. Mas o exporter tinha um `if` para
Langfuse embutido (`if settings.langfuse_public_key and ...`), com endpoint e headers
montados ali. Cada novo backend com convenção própria (Phoenix, Honeycomb, Grafana
Cloud) pediria outro `if`.

## Decisão

`observability/backends.py` define **presets**: funções puras `Settings → (endpoint,
headers)`, registradas em `PRESETS`. Incluídos: `generic` (usa
`OTEL_EXPORTER_OTLP_ENDPOINT`/`HEADERS`) e `langfuse` (endpoint `/api/public/otel`,
`Authorization: Basic`, `x-langfuse-ingestion-version: 4`).

`OTEL_BACKEND=auto|generic|langfuse` escolhe; `auto` preserva o comportamento do upstream
(Langfuse quando as chaves existem). Header definido à mão nunca é sobrescrito. A chave
secreta do Langfuse passa a ser `SecretStr`.

Também: o `TracerProvider` agora é finalizado com `atexit` — no upstream, uma CLI que
encerrava logo após a resposta podia perder spans ainda no `BatchSpanProcessor`.

## Alternativas consideradas

- **Sempre exigir um OpenTelemetry Collector** — boa prática em produção e continua
  suportada (`generic`), mas pesada demais para desenvolvimento local.

## Consequências

- Novo backend = nova função de ~5 linhas em `PRESETS`, testável sem rede.
- O núcleo continua sem nenhuma dependência de SDK de observabilidade.
