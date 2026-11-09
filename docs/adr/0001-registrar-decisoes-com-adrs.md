# 0001. Registrar decisões arquiteturais com ADRs

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O upstream documenta suas decisões no README e em comentários ("Duas decisões que
sustentam o resto"). Funciona para um projeto didático de um domínio só, mas este
repositório nasce para ser reaproveitado em contextos diferentes: quem adapta precisa
saber *por que* cada peça é como é antes de mudá-la, e as diferenças em relação ao
upstream precisam ser rastreáveis.

## Decisão

Registrar cada decisão arquitetural relevante em `docs/adr/NNNN-titulo.md`, no formato
Contexto / Decisão / Alternativas / Consequências. Os documentos de design
(`docs/design/`) descrevem *como o sistema é*; os ADRs explicam *por que ficou assim*.

## Alternativas consideradas

- **Só README** — mistura guia de uso com justificativa; cresce sem estrutura.
- **Wiki do GitHub** — fica fora do versionamento junto do código.

## Consequências

- Mudanças estruturais passam a vir acompanhadas de um ADR no mesmo PR.
- Um ADR aceito não é editado; uma mudança de rumo gera um novo que o substitui.
