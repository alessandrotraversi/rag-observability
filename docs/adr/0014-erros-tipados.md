# 0014. Erros tipados na biblioteca; só as CLIs encerram o processo

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream trata falhas de configuração com `print(..., file=sys.stderr)` seguido de
`raise SystemExit(1)` dentro de funções de biblioteca (`ensure_collection_ready`,
`ensure_planner_covers_index`, `validate_observability_policy`). Embutido num servidor,
isso derruba o processo em vez de deixar o chamador decidir.

## Decisão

Hierarquia em `core/errors.py`: `RagError` → `ConfigurationError`,
`IndexNotReadyError`, `IndexContractError`, `IngestionError`, `IndexingError`,
`ScopeError`. A biblioteca só levanta exceções; as CLIs capturam `RagError`, imprimem e
encerram; a API converte `ScopeError` em 403 e o resto em 500 genérico.

## Consequências

- Mensagens de erro continuam claras para o operador, sem matar processos hospedeiros.
- Os testes verificam condições de erro com `pytest.raises`.
