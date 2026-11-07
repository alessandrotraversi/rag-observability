# 0010. Tabela de preços externa, custo por modelo e fail-fast

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

No upstream, o custo estimado usa um único par de preços fictícios no código
(`INPUT_USD_PER_MILLION = 0.15`, `OUTPUT_USD_PER_MILLION = 0.60`) aplicado à soma de
tokens de **todos** os modelos. Com mais de um modelo permitido, ou outro provedor, a
estimativa fica errada; e trocar preço exige deploy de código.

## Decisão

- Preços em `config/pricing.yaml` (`AI_PRICING_PATH`), por modelo, em USD por milhão de
  tokens de entrada e saída, com `default` opcional.
- Resolução por nome exato e, em seguida, pelo **prefixo mais longo** (provedores
  reportam snapshots datados, como `gpt-4.1-mini-2025-04-14`).
- Custo calculado **por modelo** a partir do uso por modelo do
  `UsageMetadataCallbackHandler`.
- **Fail-fast:** na subida, todo modelo em `AI_ALLOWED_MODELS` precisa ter preço (ou
  existir `default`). Sem isso a aplicação não sobe: um modelo sem preço custaria
  "zero" e passaria pelo orçamento sem ser contado.

## Alternativas consideradas

- **Buscar preços de uma API do provedor** — não há fonte padronizada; adiciona
  dependência de rede na subida.
- **Custo zero para modelo desconhecido** — falha silenciosa no controle de gasto.

## Consequências

- Continua sendo **estimativa**, não billing. Os valores do arquivo são exemplos e devem
  ser conferidos com a tabela vigente do provedor.
- O custo aparece igual em spans (`rag.cost.estimated_usd`), log e debug (com
  detalhamento por modelo).
