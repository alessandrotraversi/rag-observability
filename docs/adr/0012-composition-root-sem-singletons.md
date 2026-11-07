# 0012. Composition root e injeção de dependências, sem singletons globais

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

No upstream, `settings = Settings()` é criado na importação de `app/config.py` e todo
módulo o importa; `api.py` instancia `RagPipeline()` na importação. Consequências:
importar qualquer módulo exige `.env` válido, testes não conseguem variar configuração,
e não dá para ter dois pipelines (dois profiles) no mesmo processo.

## Decisão

- `load_settings()` cria Settings sob demanda; nada lê ambiente na importação.
- `rag_observability/bootstrap.py` é o **composition root**: monta telemetria, profile,
  preços, ledger, política, índice e modelos, e devolve um `Container`.
- `RagPipeline` recebe tudo pelo construtor (`profile`, `index`, `steps`, `policy`,
  `telemetry`, `feature`).
- A API expõe `create_app(container=None, scope_resolver=None)`; o atributo `app` para o
  uvicorn é criado preguiçosamente.

## Alternativas consideradas

- **Framework de DI** — desnecessário para um grafo deste tamanho.

## Consequências

- Vários pipelines (profiles diferentes) podem coexistir no mesmo processo.
- Embutir o pipeline em outra aplicação é chamar `build_container(settings)`.
- O `TracerProvider` do OpenTelemetry continua global por natureza; `Telemetry.setup()`
  o configura uma única vez por processo.
