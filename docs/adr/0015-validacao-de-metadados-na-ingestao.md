# 0015. Contrato de metadados validado na ingestão e na subida

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream identificou o risco central do filtro eliminatório: um valor de metadado que
o planner não sabe produzir faz o documento sumir de toda busca filtrada. A defesa era
uma checagem na subida (`ensure_planner_covers_index`) para dois campos fixos.

## Decisão

Defesa em duas camadas, para **todas** as facetas do profile:

1. **Ingestão** (`ingestion/chunking.py: validate_metadata`): além dos
   `required_metadata`, todo documento com valor fora de `values` (ou do `wildcard`) de
   uma faceta é rejeitado com mensagem que cita arquivo, campo e valores aceitos.
2. **Subida** (`RagPipeline.check_index_contract`): consulta `distinct_values` de cada
   campo de faceta no índice e recusa iniciar se houver valor não declarado (cobre
   índices construídos por outro processo ou versão anterior do profile).

O `cli.doctor` executa a mesma checagem sem gastar tokens.

## Consequências

- O erro aparece no momento mais barato (ao ingerir), não como "não encontrei" em
  produção.
- Adicionar um valor de faceta exige atualizar o profile — intencional: o catálogo do
  planner precisa descrever o novo valor.
