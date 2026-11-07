# 0008. Telemetria: namespace `rag.*` e `gen_ai.*` em toda chamada de modelo

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream usa `ai.rag.*` nos spans, `app.*` nos atributos e as semantic conventions de
GenAI (`gen_ai.*`) **só** no span de resposta. Consequências observadas:

- planner e reranker também chamam o modelo, mas o Langfuse os mostra como spans comuns,
  sem tokens: o custo por etapa fica invisível;
- `app.*` descreve "esta aplicação", não o conceito; duas aplicações no mesmo backend
  colidem;
- atributos de domínio (`app.doc_types`, `app.plan`, `app.tenant`) não existem em
  outros domínios.

## Decisão

- Spans: `rag.pipeline` (raiz), `rag.query_planning`, `rag.retrieval`, `rag.reranking`,
  `rag.answer_generation`.
- Atributos do pipeline em `rag.*`, agrupados por assunto: `rag.query.*`,
  `rag.retrieval.*`, `rag.rerank.*`, `rag.policy.*`, `rag.budget.*`, `rag.cost.*`,
  `rag.duration.*`, `rag.usage.*`.
- Atributos de domínio gerados de forma genérica: `rag.scope.<campo>` e
  `rag.query.facet.<faceta>`; mais `rag.profile` para filtrar por domínio.
- **Toda** chamada de modelo recebe `gen_ai.operation.name`, `gen_ai.provider.name`,
  `gen_ai.request.model`, `gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
  `gen_ai.response.model` e `gen_ai.usage.*` — com tokens medidos por etapa.
- Resource ganha `service.version` e `deployment.environment.name`.
- Erros: além do status, `error.type`.
- Todos os nomes vivem em `observability/conventions.py`.

Mantido do upstream sem alteração: só atributos seguros; pergunta/resposta apenas como
eventos de debug em development; sampler `ParentBased(TraceIdRatioBased)`; development
sempre 1.0; `OBSERVABILITY_CAPTURE_CONTENT=true` fora de development impede a subida.

## Alternativas consideradas

- **Manter `app.*`** — compatível com dashboards do upstream, mas perpetua o acoplamento.
- **Prefixo configurável** — flexibilidade que fragmenta dashboards entre deploys.

## Consequências

- **Quebra** dashboards/consultas feitos sobre os nomes do upstream; a tabela de
  equivalência está em `docs/design/07-diferencas-upstream.md`.
- No Langfuse, as três etapas aparecem como *generations* com custo — o que é correto.
