# 2. Domain Profile — especificação

Arquivo YAML selecionado por `RAG_PROFILE`. Validado por
`rag_observability/domain/profile.py` na subida; qualquer erro impede a aplicação de
iniciar com uma mensagem que aponta o campo. Caminhos relativos (`ingestion.source_dir`)
são resolvidos a partir do diretório do próprio profile.

## Esquema

| Chave | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `name` | str | — | Identificador; vai para spans (`rag.profile`) e logs |
| `description` | str | `""` | Livre |
| `collection` | str | — | Nome da coleção/tabela no vector store (alfanumérico/underscore) |
| `assistant.domain` | str | — | Nome do domínio, usado nos prompts ("for {domain}") |
| `assistant.persona` | str | `an assistant` | Quem responde |
| `assistant.language` | str | `English` | Idioma da resposta, da reescrita e da pergunta de esclarecimento |
| `scope.enforced_filters` | map | `{}` | Filtros de autorização sempre aplicados |
| `scope.request_fields` | list | `[]` | Campos que um chamador confiável informa por requisição (obrigatórios quando declarados) |
| `scope.observed_fields` | list | todos | Campos de escopo que viram atributos de span e chave de orçamento |
| `facets[]` | list | `[]` | Ver abaixo |
| `planner.guidance` | list[str] | `[]` | Regras extras do domínio, acrescentadas às regras do método |
| `planner.clarification_guidance` | str | `""` | O que conta como ambíguo neste domínio |
| `planner.examples` | list[str] | `[]` | Few-shot do planner |
| `ingestion.loader` | str | `markdown` | Loader embutido ou `pacote.modulo:funcao` |
| `ingestion.source_dir` | path | `knowledge_base` | Relativo ao profile |
| `ingestion.glob` | str | `*.md` | |
| `ingestion.required_metadata` | list | `[title]` | Front matter obrigatório |
| `ingestion.context_header` | list[{label, field}] | título + seção | Cabeçalho prefixado em cada chunk (chega ao embedding) |
| `ingestion.split_headers` | list | `#`,`##`,`###` | Níveis de heading para o primeiro corte |
| `ingestion.chunk_size` / `chunk_overlap` | int | 900 / 150 | Segundo corte, por tamanho |
| `retrieval.top_k` | int | 8 | Candidatos do retrieval (recall) |
| `retrieval.rerank_top_n` | int | 4 | Máximo que segue para a resposta (precisão); ≤ `top_k` |
| `retrieval.preview_chars` | int | 300 | Tamanho do preview no debug |
| `sources.extra_fields` | list | `[]` | Metadados expostos em cada fonte citada, além de arquivo/título/seção |
| `messages.no_answer` | str | (inglês) | Resposta quando o contexto não sustenta |
| `messages.clarification_fallback` | str | (inglês) | Se o planner pedir esclarecimento sem formular a pergunta |
| `messages.policy_blocked` | str | (inglês) | Resposta controlada de bloqueio de política |

### Faceta

| Chave | Tipo | Descrição |
| --- | --- | --- |
| `name` | identificador | Nome do campo no QueryPlan (não pode ser `normalized_question`, `exact_terms`, `needs_clarification`, `clarification_question`) |
| `field` | identificador | Campo de metadado; padrão = `name` |
| `description` | str | Instrução ao planner sobre quando/como preencher |
| `multiple` | bool | `true`: lista com **todo** valor que possa conter a resposta; `false`: um valor ou nulo |
| `values` | map valor→descrição | Vocabulário fechado; vira `Literal` no schema |
| `wildcard` | str? | Valor de documento que casa com qualquer seleção (ex.: `all`); nunca escolhível |

## Regras de validação

- Nomes de faceta únicos, identificadores válidos e não reservados.
- Nenhuma faceta pode usar um campo de `scope.enforced_filters` (o modelo nunca mexe em
  autorização).
- `retrieval.rerank_top_n ≤ retrieval.top_k`.
- Na ingestão: todo valor de metadado de faceta deve estar em `values` ou ser o
  `wildcard`.
- Na subida: os valores distintos do índice para cada campo de faceta devem estar
  declarados.

## Exemplos incluídos

- `profiles/fcai-saas-support/` — o domínio original do upstream, equivalente 1:1.
- `profiles/hr-handbook/` — manual de RH em inglês, multi-empresa via
  `request_fields: [company]`, com documento `draft` que o filtro fixo
  `status: approved` precisa esconder.

## Como criar um profile novo

1. Copie `profiles/hr-handbook/` para `profiles/<seu-dominio>/`.
2. Coloque seus Markdown em `knowledge_base/` com front matter.
3. Declare em `facets` só as dimensões que **ajudam a busca** e têm vocabulário fechado.
   Na dúvida, menos facetas: um filtro errado esconde a resposta.
4. Escreva 2–4 exemplos de planner cobrindo: pergunta direta, pergunta ambígua e
   pergunta que vale para todos os valores.
5. `RAG_PROFILE=profiles/<seu-dominio>/profile.yaml python -m rag_observability.cli.doctor`.
