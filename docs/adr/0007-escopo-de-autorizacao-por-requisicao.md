# 0007. Escopo de autorização: filtros fixos + escopo por requisição resolvido no servidor

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

Uma das melhores decisões do upstream: tenant, produto e status são filtros que a
aplicação aplica sempre (`SAFE_FILTERS`), fora do alcance do modelo. Mas eram constantes
— um único tenant por deploy. Num produto real multi-tenant, o tenant vem da identidade
do usuário, a cada requisição.

## Decisão

O profile declara dois tipos de escopo:

- `scope.enforced_filters` — fixos, aplicados em toda requisição;
- `scope.request_fields` — campos que um **chamador confiável** informa por requisição
  (`pipeline.run(question, scope={"company": "acme-labs"})`).

`resolve_scope()` garante que a requisição não sobrescreve um filtro fixo, não introduz
campo não declarado e não omite um campo declarado (omitir alargaria a busca em
silêncio). Violação gera `ScopeError` → HTTP 403.

Facetas não podem filtrar campos de escopo (validado no profile): o modelo nunca alarga
nem estreita autorização.

Na API, o escopo vem de um `ScopeResolver` injetável. O padrão é **nenhum** escopo do
cliente; `API_SCOPE_FROM_HEADERS=true` lê `X-RAG-Scope-<campo>` e só deve ser ligado
atrás de um gateway que preenche esses headers a partir da autenticação.

## Alternativas consideradas

- **Escopo no corpo do `/chat`** — o usuário escolheria o próprio tenant.
- **Um deploy por tenant** — o que o upstream implica; não escala.

## Consequências

- `scope.observed_fields` define quais campos de escopo viram atributos de span
  (`rag.scope.<campo>`) e chave do orçamento (ADR 0011).
- Integradores devem fornecer seu próprio resolver em `create_app(scope_resolver=...)`.
