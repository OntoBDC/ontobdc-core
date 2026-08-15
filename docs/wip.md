# Work in Progress

Atualizado em 2026-08-12. Este documento resume o estado atual dos dois pacotes que compõem a stack (`ontobdc` e `ontobdc-view`/`presentation`) e aponta para o `CHANGELOG.md` de cada um para o detalhe completo — o que está aqui é a versão condensada.

## Versões atuais

| Pacote | Repositório | Versão publicada (`pyproject.toml`) | Branch em desenvolvimento | Status |
| --- | --- | --- | --- | --- |
| `ontobdc` | `ontobdc-wip` | 0.14.0 | `v0.15` | PR aberto: [ontobdc-wip#104](https://github.com/EliasMPJunior/ontobdc-wip/pull/104) |
| `ontobdc_view` (presentation) | `ontobdc-view` | 0.1.0 | `v0.2` | PR aberto: [ontobdc-view#1](https://github.com/EliasMPJunior/ontobdc-view/pull/1) |

As duas branches estão sincronizadas com seus respectivos `origin` e prontas para revisão — nenhum commit local pendente. `master` é a branch padrão dos dois repositórios; `v0.15`/`v0.2` são as branches versionadas onde o trabalho corrente acontece até serem mergeadas.

## Resumo do changelog — `ontobdc` (v0.15)

Ver `CHANGELOG.md` (seção `Unreleased`) para o detalhe completo. Destaques desta rodada:

- **Mecanismo genérico de páginas de entidade**: novo `PagePort`/`PageMetadata`, estado final `entity_views_published` e `EntityViewsPublishedCapability`, que publica uma página HTML por entidade sem `ontobdc` conhecer o tipo específico da entidade — toda a renderização fica em `ontobdc_view`. Substitui o `DatasetViewsGeneratedCapability` antigo, que era código morto (nunca chegou a importar).
- **`ComponentSourcePort`**: elimina o dicionário hardcoded que `SurfacePackagedCapability` usava para localizar os builders de tema/marca/idioma/foto em `ontobdc_view`.
- **Correções reais no runtime de anotação** (achadas testando ao vivo no navegador): construção do worker do pdf.js via `blob:` (contornando bloqueio de redirect cross-origin do Chrome), overlay de geometria bloqueando cliques em marcadores existentes, dessincronia entre a toolbar e o modo real do controlador de geometria, seletor de categoria que continuava visível mesmo escondido via `hidden`, clique num marcador existente sendo sequestrado pela criação de um novo ponto de geometria, e um bug de truncamento (`createWritable`) que corrompia o arquivo de anotações ao salvar.
- **Redução de escopo do editor de anotação**: por enquanto só existe `NoteAnnotation` com ferramenta `point` — categoria e demais ferramentas de geometria continuam no código (comentadas/ocultas, não removidas) e voltam a ser expostas conforme [ontobdc-wip#103](https://github.com/EliasMPJunior/ontobdc-wip/issues/103).

## Resumo do changelog — `ontobdc_view` / presentation (v0.2)

Ver `CHANGELOG.md` (seção `Unreleased`) para o detalhe completo. Destaques desta rodada:

- **Página de detalhe 5W2H do WorkStream**: nova categoria de plugin `page/` (espelhando `component/`), com `WorkStreamViewPage` e `render_entity_view()`. A página replica fielmente a identidade visual dos Tiles — 7 cards independentes (What/Why/Who/Where/When/How/HowMuch), cada um com sua própria árvore de recursos (Related/Found), preview e edição de relação recurso↔dimensão via pyodide + rdflib (carregado sob demanda, só quando o usuário relaciona/desrelaciona algo pela primeira vez).
- **Runtime de anotação finalmente conectado**: o runtime já existia empacotado em `ontobdc` mas nunca tinha um host real; agora está ligado à página do WorkStream (conectar pasta via File System Access API, criar/ver anotações por dimensão, Workspace/Subjects no cabeçalho). Anotações passaram a salvar dentro do próprio dataset (`payload/triple/EnrichmentAnnotation.ttl`), não mais num bucket genérico do container.
- **Correções de UX encontradas em teste ao vivo**: árvore de recursos (era lista plana), botões de anotação permanentemente desabilitados, popups de Workspace/Subjects ilegíveis (texto claro sobre fundo claro) e com layout quebrado (colisão de nome de classe CSS entre o editor e o popup), ícone que sumia após o primeiro uso, cards com largura inconsistente.

## Pendências conhecidas

- `ontobdc_view` ainda não está publicado no PyPI nem declarado como dependência formal de `ontobdc` (import é best-effort, silenciosamente vazio se ausente).
- Categoria completa de anotação (Issue/Classification/Location/Record) e ferramentas de geometria além de `point` — [ontobdc-wip#103](https://github.com/EliasMPJunior/ontobdc-wip/issues/103).
- PRs `v0.15 → master` e `v0.2 → master` ainda não revisados/mergeados.
