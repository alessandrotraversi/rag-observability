# 0002. Domínio declarado em um Domain Profile (YAML), fora do código

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

No upstream, o domínio (a empresa fictícia FCAI) está espalhado pelo código:

| Onde | O que é específico do domínio |
| --- | --- |
| `app/query_planner.py` | `SAFE_FILTERS = {"tenant": "fcai", ...}`, `DocType`, `Plan`, `ALL_PLANS`, o catálogo inteiro no `PLANNER_SYSTEM_PROMPT` e os exemplos |
| `app/rag_pipeline.py` | `"You are a support assistant for FCAI"`, "Write 'answer' in Portuguese", as mensagens de recusa/bloqueio |
| `app/ingest.py` | `REQUIRED_METADATA`, `CONTEXT_HEADER_FIELDS`, tamanho de chunk, diretório |
| `app/index.py` | `TABLE_NAME = "fcai_knowledge_base"` |
| `app/rerank.py`, `app/retrieve.py` | campos `version`, `plan`, `doc_type` impressos à mão |

Aplicar a solução a outro contexto exigia editar seis arquivos Python, e qualquer
esquecimento quebrava em silêncio (um `doc_type` novo que o planner não conhece some de
toda busca filtrada).

## Decisão

Todo conhecimento de domínio vive em um **Domain Profile** — um arquivo YAML validado
por Pydantic (`rag_observability/domain/profile.py`), selecionado por `RAG_PROFILE`.
Ele declara: assistente (domínio, persona, idioma), escopo de autorização, facetas,
orientação e exemplos do planner, ingestão, retrieval, campos de citação e mensagens.

A separação de responsabilidades fica:

- **Profile** → *sobre o quê* o assistente fala (muda por domínio);
- **Settings / `.env`** → *onde e com quê* ele roda (muda por ambiente);
- **Código** → *o método* (as regras que todo RAG desse formato precisa).

O exemplo original virou `profiles/fcai-saas-support/`; um segundo domínio sem relação
(`profiles/hr-handbook/`, em inglês, multi-empresa) prova que o núcleo é agnóstico.

## Alternativas consideradas

- **Subclasses por domínio** (`class FcaiPipeline(RagPipeline)`) — exige programar para
  cada contexto e espalha o domínio de novo.
- **Variáveis de ambiente** — não comportam estruturas (facetas com descrições por valor,
  exemplos few-shot).
- **Banco de dados de configuração** — complexidade desnecessária; YAML versionado junto
  da base de conhecimento é revisável em PR.

## Consequências

- Um novo contexto é um diretório `profiles/<nome>/` com `profile.yaml` + documentos.
- O profile é validado na subida: nomes de faceta inválidos/reservados, faceta sobre
  campo de autorização, `rerank_top_n > top_k` e coleção com nome inseguro são rejeitados.
- O prompt passa a ser *montado*: perde-se um pouco da liberdade de escrever o prompt
  inteiro à mão; em troca, o método (regras) e o domínio (catálogo) evoluem separados.
  `planner.guidance` e `planner.examples` cobrem as nuances de cada domínio.
