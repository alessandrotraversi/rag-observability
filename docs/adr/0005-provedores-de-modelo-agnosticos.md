# 0005. Provedores de modelo via `init_chat_model` / `init_embeddings`

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream fixa `model_provider="openai"`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` e
`OpenAIEmbeddings`. Organizações diferentes têm provedores diferentes (Azure OpenAI,
Bedrock, Vertex, Anthropic, modelos locais com Ollama) por custo, residência de dados ou
contrato.

## Decisão

- `LLM_PROVIDER` + `LLM_MODEL` → `langchain.chat_models.init_chat_model`;
- `EMBEDDING_PROVIDER` + `EMBEDDING_MODEL` → `langchain.embeddings.init_embeddings`;
- credenciais por `LLM_API_KEY`/`EMBEDDING_API_KEY` (opcionais, `SecretStr`) ou pela
  variável nativa do provedor (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...);
- `OPENAI_CHAT_MODEL`/`OPENAI_EMBEDDING_MODEL` continuam aceitos como aliases, para
  migrar um `.env` do upstream sem editar.

Os pacotes de integração viram dependências opcionais (`pip install .[anthropic]`), e
`rag_observability.cli.doctor` verifica se o pacote do provedor está instalado.

## Alternativas consideradas

- **Interface própria de LLM** — reimplementaria o que a LangChain já padroniza
  (structured output, callbacks de uso).
- **LiteLLM** — boa opção, mas adicionaria uma segunda abstração ao lado da LangChain,
  que o projeto já usa.

## Consequências

- O pipeline depende de structured output: o modelo escolhido precisa suportar tool
  calling / JSON schema. Modelos locais pequenos podem falhar no planner.
- Trocar de modelo de embeddings invalida os vetores: o manifest guarda um
  *fingerprint* (provedor, modelo, store) e força rebuild quando ele muda.
- `gen_ai.provider.name` nos spans passa a refletir o provedor real.
