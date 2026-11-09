# 0003. Schema do QueryPlan gerado dinamicamente a partir das facetas

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream define o plano de busca como uma classe fixa:

```python
DocType = Literal["sla", "policy", "product", "plan", "company"]
Plan = Literal["starter", "pro", "enterprise"]
class QueryPlan(BaseModel):
    doc_types: list[DocType]; plan: Plan | None; ...
```

Os `Literal` são o que garante, via structured output, que o modelo só devolve valores
existentes. É uma boa decisão — mas amarra o schema ao domínio.

## Decisão

Generalizar o conceito como **facetas**: dimensões de metadados com vocabulário fechado.
Cada faceta do profile tem `name`, `field`, `values` (valor → descrição), `multiple`
(lista ou valor único) e um `wildcard` opcional (o antigo `plan: all`).

Na subida, `build_query_plan_model(profile)` usa `pydantic.create_model` para gerar o
`QueryPlan` sobre uma base fixa (`normalized_question`, `exact_terms`,
`needs_clarification`, `clarification_question`) mais um campo por faceta, com
`Literal[...]` dos valores declarados. O wildcard nunca entra no `Literal`: o modelo não
pode escolhê-lo, só os documentos podem tê-lo.

`facet_selections()` normaliza o plano em `{faceta: [valores]}` e `build_filters()`
transforma isso em filtros, acrescentando o wildcard quando existe.

## Alternativas consideradas

- **Campo genérico `filters: dict[str, list[str]]`** — perde o `Literal`; o modelo
  passaria a inventar valores e o filtro eliminatório esconderia respostas.
- **Gerar código Python a partir do YAML** — passo de build extra sem ganho.

## Consequências

- As garantias do upstream continuam (valores fechados, wildcard, "na dúvida, sem
  filtro"), agora para qualquer número de facetas.
- O nome da faceta vira nome de campo no schema JSON enviado ao modelo: precisa ser
  identificador válido e não colidir com os campos fixos (validado no profile).
- Spans e debug passam a falar de facetas de forma genérica (`rag.query.facet.<nome>`)
  em vez de `app.doc_types`/`app.plan`.
