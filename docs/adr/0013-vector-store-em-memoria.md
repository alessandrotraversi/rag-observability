# 0013. Vector store em memória com persistência em arquivo

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

Para experimentar o upstream é preciso Docker com pgvector antes da primeira pergunta.
Para testar o pipeline, idem. Isso pesa em quem só quer avaliar se a solução serve para
o seu contexto.

## Decisão

Adicionar `VECTOR_STORE=memory`: `InMemoryIndex`, busca exata por similaridade de
cosseno, persistida em `data/<collection>/memory_index.json` para sobreviver entre
`index` e `chat`. O score é **distância** de cosseno (menor = mais próximo), a mesma
convenção do pgvector, para que debug e spans sejam comparáveis.

## Alternativas consideradas

- **FAISS / Chroma** — dependências nativas extras para um caso de "primeiros passos".
- **`InMemoryVectorStore` da LangChain** — sem persistência nem `distinct_values`.

## Consequências

- Quickstart sem infraestrutura (só a chave do provedor de modelos).
- É força bruta O(n) e um arquivo JSON: adequado a milhares de chunks, **não** a
  produção. O pgvector segue como padrão.
- Serve de implementação de referência da DSL de filtros (ADR 0006) e é usado nos testes.
