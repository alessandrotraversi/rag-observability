# 0011. Ledger de uso como porta; orçamento por feature + escopo observado

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream grava o uso em `data/ai_usage.jsonl` e relê o arquivo inteiro a cada
requisição para somar o gasto do mês do par `tenant`/`feature`. O próprio README avisa:
não escala, sem coordenação entre processos. Além disso, a chave do orçamento é sempre
`tenant`, que nem todo domínio tem.

## Decisão

- `UsageLedger` vira porta com `record()` e `spend_since(since, feature, scope)`.
- Adapters: `jsonl` (comportamento do upstream, agora com lock entre threads),
  `memory` (testes) e `none` (sem orçamento). Produção pluga o seu
  (`AI_USAGE_LEDGER=meu_pacote.ledger:RedisLedger`).
- O orçamento é por `feature` + **escopo observado** (`scope.observed_fields` do
  profile), um dicionário arbitrário: `{tenant, product}` no FCAI, `{company}` no HR.
- O registro passa a ter `provider` e uma linha **por modelo** usado na execução.
- O início do mês é calculado por um relógio injetável (`PolicyEngine(clock=...)`), e a
  comparação é por data, não por prefixo de string.

Mantido: a política é decidida antes de qualquer chamada de modelo; bloqueio não é erro
(HTTP 200, `policy_blocked: true`); só execuções que chamaram o modelo entram no ledger.

## Alternativas consideradas

- **Contador em Redis embutido** — força infraestrutura no quickstart.
- **Manter a chave `tenant` fixa** — inválida em domínios sem tenant.

## Consequências

- O formato da linha do JSONL muda (`scope` como objeto, `provider`); ledgers antigos não
  são somados no novo esquema.
- A verificação "gasto ≥ orçamento" continua não-atômica em relação ao registro; um
  ledger de produção deve reservar/consumir de forma transacional.
