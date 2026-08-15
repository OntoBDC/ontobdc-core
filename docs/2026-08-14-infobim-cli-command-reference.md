# InfoBIM CLI Command Reference

> **Data**: 2026-08-14
> **Auditoria**: `src/infobim/**/plugin/command/*.py` (produção) + apêndice `src/old/` (legado).
> **Ponto de vista**: usuário final do entry-point `infobim`.

O InfoBIM é a camada de domínio BIM/OpenBIM construída **em cima** do OntoBDC. A maioria
dos comandos de *storage* e *view* é um **proxy inteligente** para o comando equivalente
do OntoBDC, mas com **resolução de `IfcProject GlobalId`** (via `ProjectIdStrategy`)
e validação que o container realmente cumpre o contrato de InfoBIM Project (carrega o
dataset reservado `ifb_01`, ou outro nomeado por `PROJECT_DATASET_NAME`).

---

## Sumário executivo

| Domínio lógico | Comandos reais | Helpers de ajuda | Sub-componente exclusivo InfoBIM |
|---|---|---|---|
| `cli` (bootstrap) | 2 | 1 (welcome) | `--version` específico InfoBIM |
| `project` (ciclo de vida do container BIM) | 5 | 1 | `--project-id/--project` + `ProjectIdStrategy` |
| `ifc` (domínio exclusivo) | 3 | 1 | **Novo:** listar classes / elementos / IFC por GlobalId |
| `context` (entidades) | 1 | 1 | Proxy com modo exclusivo para `IfcWorkSchedule` |
| `view` (Surface) | 1 | 1 | Proxy com 3 componentes visuais IFC injetados |
| **Total atual** | **12 comandos de operação** | **5 help** |  |

---

## 1 · Componente `cli` (entrada e bootstrap)

### 1.1. `welcome` — banner de entrada

- **ID metadata**: `welcome`
- **Classe**: `InfoBIMWelcomeCommand`
- **Arquivo**: [welcome.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/cli/plugin/command/welcome.py)
- **Formato de rota (argv)**: `infobim` (zero argumentos)
- **Uso usuário**:
  ```bash
  infobim
  ```
- **O que o usuário percebe**:
  - Sem argumento algum, o CLI mostra o banner "InfoBIM" com a versão instalada.
  - Abaixo do banner é impressa a **tabela de todos os comandos descobertos** em todos os
    domínios lógicos registrados (buildada por `build_command_table`).
- **Guardas / `check()`**: Falha se qualquer argumento for passado (redireciona para
  outro comando). Não tem efeito colateral — pura renderização textual.
- **Resposta**: `HelpCommandResponse` com `{Usage: [...], Commands: tabela_completa}`.

### 1.2. `init` — inicializar workspace (re-export OntoBDC)

- **ID metadata**: idêntico ao `ontobdc init` (re-export simples).
- **Classe**: `CliInitCommand`
- **Arquivo**: [init.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/cli/plugin/command/init.py)
- **Observação**: Não existe comportamento InfoBIM-específico aqui — é um
  `from ontobdc.cli.plugin.command.init import CliInitCommand` direto. O único
  propósito é registrar o mesmo comando sob o domínio "cli" do InfoBIM, para que
  o `CommandLoader` o descubra no entry-point `infobim init`.
- **Uso usuário**:
  ```bash
  infobim init
  ```

### 1.3. `version` — versão do pacote `infobim`

- **ID metadata**: `version`
- **Classe**: `InfoBIMVersionCommand`
- **Arquivo**: [version.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/cli/plugin/command/version.py)
- **Formato de rota (argv)**: `infobim --version` ou `infobim -v`
- **Uso usuário**:
  ```bash
  infobim --version
  infobim -v
  ```
- **O que o usuário percebe**: Devolve a versão **específica do InfoBIM** (campo
  `__version__` de `infobim/__init__.py`), não a versão do OntoBDC.
- **Resposta**: `CommandResponse{version: "<X.Y.Z>"}`.

---

## 2 · Componente `project` (ciclo de vida do Projeto BIM)

> Todos esses comandos operam em torno da **estratégia central** `ProjectIdStrategy`:
> dado um path, um GlobalId, ou um selector, ela resolve `project_id` (IfcProject GlobalId),
> `container_id` (UUID OntoBDC) e `project_path` (diretório do container). Se o container
> registrado **não carrega** um dataset válido de IfcProject reservado, ele é
> **silentemente desconsiderado** pelos comandos de listagem e atualização.

### 2.1. `project_create` — criar novo Projeto InfoBIM vazio

- **ID metadata**: `project_create`
- **Classe**: `ProjectCreateCommand`
- **Arquivo**: [create.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/project/plugin/command/create.py)
- **State machine usada**: `ProjectCreateStateTransitionHandler` (YAML padrão
  `standard_project_create.yaml`, definido em `project/domain/machine/`).
- **Formato de rota**: `infobim project --create <path>`
- **Uso usuário**:
  ```bash
  infobim project --create ~/projetos/meu-empreendimento
  ```
- **O que o usuário percebe**: Cria um **container OntoBDC de cara InfoBIM** em
  `<path>`, com o dataset reservado `PROJECT_DATASET_NAME` (o "esqueleto de Projeto
  IfcProject"). Resolve `~` e paths relativos para absolutos automaticamente.
- **Guardas / `check()`**: `--create` exige **exatamente 1 valor não-vazio**. Nenhuma
  outra flag é aceita. O path é gravado simultaneamente nos parâmetros de contexto
  `container_path` **e** `project_path` (são a mesma entidade no InfoBIM).
- **Resposta**: `CommandResponse` do `ProjectCreateStateTransitionHandler.execute()`.

### 2.2. `project_list` — listar Projetos InfoBIM registrados

- **ID metadata**: `project_list`
- **Classe**: `ProjectListCommand`
- **Arquivo**: [list.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/project/plugin/command/list.py)
- **Formato de rota**: `infobim project --list` ou `infobim project -l`
- **Uso usuário**:
  ```bash
  infobim project --list
  infobim project -l
  ```
- **O que o usuário percebe**:
  - Pega a **lista geral** de containers registrados pelo OntoBDC (`StorageBaseCommand --list`).
  - **Filtra silenciosamente** só os containers que realmente têm um dataset InfoBIM
    válido (via `ProjectIdStrategy._project_id_for_container`).
  - Devolve um array com `{project_id, container_id, project_path}` para cada um.
- **Dica do usuário**: Se você rodar `ontobdc --list` verá containers a mais; use
  `infobim project --list` se só quiser os que são de fato Projetos BIM.
- **Resposta**: `CommandResponse{title="InfoBIM Projects", content.projects:[...]}`.

### 2.3. `project_attach` — anexar um Projeto importado externamente

- **ID metadata**: `project_attach`
- **Classe**: `ProjectAttachCommand`
- **Arquivo**: [attach.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/project/plugin/command/attach.py)
- **Roteamento**: Proxy para `StorageAttachCommand` do OntoBDC.
- **Formato de rota**: `infobim project --project-path <path> --attach`
- **Uso usuário**:
  ```bash
  infobim project --project-path /mnt/hd-externo/projeto-obra-recebido --attach
  ```
- **O que o usuário percebe**:
  1. Valida que `<path>` é diretório.
  2. Valida que dentro dele **existe** a pasta reservada `PROJECT_DATASET_NAME`
     (ex: `ifb_01`) — se não existir, `ValueError` explícito:
     `Not an InfoBIM Project: missing <dataset_name> in <path>`.
  3. Chama `ontobdc storage --container-path <path> --attach` internamente.
  4. Renomeia o título da resposta de "Storage Container Attached" para
     "InfoBIM Project Attached".
- **Guardas / `check()`**: Exatamente 3 tokens (`--project-path <valor> --attach`).

### 2.4. `project_update` — reprocessar o Projeto

- **ID metadata**: `project_update`
- **Classe**: `ProjectUpdateCommand`
- **Arquivo**: [update.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/project/plugin/command/update.py)
- **Roteamento**: Proxy para `StorageUpdateCommand` do OntoBDC.
- **Formato de rota** (3 formas válidas):
  1.  ```bash
      # dentro do próprio diretório do projeto
      infobim project --update
      ```
  2.  ```bash
      # via GlobalId do IfcProject
      infobim project --project-id 2O2Fr$t4X7Zf8NOew3FNld --update
      ```
  3.  ```bash
      # via selector ou path do container
      infobim project --project obra-XXXXX --update
      ```
- **O que o usuário percebe**:
  - Executa a estratégia `ProjectIdStrategy` para resolver `project_id` + `container_id`.
  - Chama o ciclo de atualização padrão do OntoBDC no container resolvido.
  - No `content` da resposta é anexado o campo `project_id` (o IfcProject GlobalId)
    para debug.
- **Guardas / `check()`**:
  - Falha com `CliCommandArgumentException` se nenhum Projeto for resolvível
    (ex: o usuário está em um diretório aleatório e não passou `--project-id`).
  - Mensagem amigável: `"Unable to resolve an InfoBIM Project. Run inside a Project or provide --project-id/--project."`

### 2.5. `project_delete` — remover Projeto do índice

- **ID metadata**: `project_delete`
- **Classe**: `ProjectDeleteCommand`
- **Arquivo**: [delete.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/project/plugin/command/delete.py)
- **Roteamento**: Proxy para `StorageDeleteCommand` do OntoBDC.
- **Formato de rota**: `infobim project --delete <IfcProject GlobalId>`
- **Uso usuário**:
  ```bash
  infobim project --delete 2O2Fr$t4X7Zf8NOew3FNld
  ```
- **O que o usuário percebe**:
  - Recebe o **GlobalId do IfcProject** (não o UUID do container — para o usuário
    de domínio BIM, o GlobalId é o identificador natural).
  - `ProjectIdStrategy` traduz `project_id` → `container_id` automaticamente.
  - Chama o delete do OntoBDC passando o `container_id` resolvido.
  - Se o título da resposta for "Container Deleted" → renomeia para "InfoBIM Project Deleted".
  - Anexa `project_id` original no `content`.
- **Guardas / `check()`**: Falha se o GlobalId não bater com nenhum container registrado
  e carregando dataset de Projeto.

### 2.6. `project_help` — ajuda do domínio `project`

- **ID metadata**: `project_help`
- **Classe**: `ProjectHelpCommand`
- **Formato de rota**: `infobim project --help` ou `-h`
- **Conteúdo**: `HelpCommandResponse` com título "InfoBIM Project" e a tabela
  help-table do domínio (`build_domain_help_content("project")`).

---

## 3 · Componente `ifc` (domínio exclusivo InfoBIM)

> Três comandos **totalmente novos** que não existem no OntoBDC. Todos leem a
> **fachada de dataset** do Projeto (pasta `dataset_facades/` do container,
> processada na transformação `ifc_project_facade_ready`) através do repositório
> central `IfcClassCatalogRepository`. O `--project-id` é obrigatório em todos.

### 3.1. `ifc_class_all` — classes IFC presentes no Projeto

- **ID metadata**: `ifc_class_all`
- **Classe**: `IfcClassAllCommand`
- **Arquivo**: [class_all.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/ifc/plugin/command/class_all.py)
- **Repositório**: `IfcClassCatalogRepository(project_path).list_classes()`
- **Formato de rota**: `infobim ifc --project-id <GlobalId> --class --all`
- **Uso usuário**:
  ```bash
  infobim ifc --project-id 2O2Fr$t4X7Zf8NOew3FNld --class --all
  ```
- **O que o usuário percebe**:
  - Tira um inventário de **todas as classes IFC** (deduplicação global) encontradas
    em **todas** as dataset facades do projeto.
  - Devolve, para cada classe: `{class_uri, class_name, element_count}` e um resumo
    `class_count` / `element_count` geral.
- **Guardas / `check()`**: Exatamente 5 tokens na rota (`ifc` + `--project-id` + valor
  + `--class` + `--all`). Se o GlobalId não corresponder a um Projeto registrado:
  `CliCommandArgumentException: "InfoBIM Project not found: <id>"`.
- **Resposta** exemplo:
  ```
  IFC Classes
  Found 47 IFC class(es) and 3841 element(s) in Project '2O2Fr$t4X...'.
  {
    project_id: '2O2Fr$t4X...',
    class_count: 47,
    element_count: 3841,
    classes: [
      {class_uri: '...IfcWallStandardCase', class_name: 'IfcWallStandardCase', element_count: 512},
      ...
    ]
  }
  ```

### 3.2. `ifc_class_elements_all` — todos os elementos de UMA classe

- **ID metadata**: `ifc_class_elements_all`
- **Classe**: `IfcClassElementsAllCommand`
- **Arquivo**: [class_elements_all.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/ifc/plugin/command/class_elements_all.py)
- **Repositório**: `IfcClassCatalogRepository(project_path).list_elements(<class>)`
- **Formato de rota**: `infobim ifc --project-id <GlobalId> --class <nome> --all`
- **Uso usuário**:
  ```bash
  infobim ifc --project-id 2O2Fr$t4X7Zf8NOew3FNld --class IfcWall --all
  infobim ifc --project-id 2O2Fr$t4X7Zf8NOew3FNld \
              --class https://standards.buildingsmart.org/IFC/DEV/IFC4_3/RC1/TC1/OWL#IfcDoor \
              --all
  ```
- **O que o usuário percebe**: Dado o **local name OU a URI completa** da classe,
  devolve a lista **completa** de GlobalIds de elementos correspondentes:
  `{elements: [{global_id, name, ...}, ...]}`.
- **Guardas / `check()`**: 6 tokens. Se o `<class>` não existir nas facades do projeto
  (payload sem `class_uri`):
  `CliCommandArgumentException: "IFC class not found in Project '<id>': <nome>"`.

### 3.3. `ifc_element` — detalhe de UM elemento por GlobalId

- **ID metadata**: `ifc_element`
- **Classe**: `IfcElementCommand`
- **Arquivo**: [element.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/ifc/plugin/command/element.py)
- **Repositório**: `IfcClassCatalogRepository(project_path).get_element(<GlobalId>)`
- **Formato de rota**: `infobim ifc --project-id <GlobalId> --element <element-global-id>`
- **Uso usuário**:
  ```bash
  infobim ifc --project-id 2O2Fr$t4X7Zf8NOew3FNld --element 3SFR5lJ8jDmPhGdE0aRz7f
  ```
- **O que o usuário percebe**: Localiza um elemento específico atravessando todas as
  dataset facades. Devolve sua classe (`class_name`, `class_uri`), propriedades
  materiais / quantitativas extraídas, localização e metadados.
- **Guardas / `check()`**: 5 tokens. Três falhas possíveis:
  1. Projeto não encontrado → `CliCommandArgumentException`.
  2. `ValueError` propagado pelo repositório → transformado em argument error.
  3. Elemento não encontrado (`found == False`):
     `"IFC element not found in Project '<id>': <global_id>"`.

### 3.4. `ifc_help` — ajuda do domínio `ifc`

- **ID metadata**: `ifc_help`
- **Classe**: `IfcHelpCommand`
- **Formato de rota**: `infobim ifc --help` ou `-h`
- **Conteúdo**: Help-table com as 3 rotas de listagem acima. Título "InfoBIM IFC"
  com descrição "Inspect IFC information exposed through Project dataset facades."

---

## 4 · Componente `context` (entidades)

### 4.1. `context_entity` — entidades do domínio via Projeto InfoBIM

- **ID metadata**: `context_entity`
- **Classe**: `InfoBIMContextEntityCommand`
- **Arquivo**: [entity.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/context/plugin/command/entity.py)
- **Estratégia de parâmetro**: `ProjectIdStrategy` (quando aplicável).
- **Formato de rota**: quatro modos, análogos aos do OntoBDC mas com prefixo `infobim context`:
  1.  **Catálogo completo** (operação global, não pede projeto):
      ```bash
      infobim context --entity --all
      ```
  2.  **Lookup URI/CURIE único** (operação global):
      ```bash
      infobim context --entity urn:ontobdc:entity:IfcWall
      infobim context --entity IfcWall
      ```
  3.  **Listar instâncias** (exige selecionar Projeto):
      ```bash
      # dentro da pasta do projeto
      infobim context --entity IfcWall
      # ou explicitamente
      infobim context --entity IfcWall --project-id 2O2Fr$t4X7Zf8NOew3FNld
      infobim context --entity IfcWall --project obra-XX
      ```
  4.  **Criar instância** (exige selecionar Projeto):
      ```bash
      infobim context \
          --create "Cronograma do Bloco A" \
          --entity IfcWorkSchedule \
          --project-id 2O2Fr$t4X7Zf8NOew3FNld
      ```
- **Ponto exclusivo InfoBIM — modo 4 especial para `IfcWorkSchedule`**:
  Quando `--entity <NomeTemLocalNameIfcWorkSchedule>` **e** `--create` está presente,
  a execução **não cai no proxy OntoBDC** e sim roda **`ContextEntityCreateService`**
  local do InfoBIM. Isso preenche a planilha de workbook / contexto específico do
  domínio de cronogramas (não a criação genérica do OntoBDC). Qualquer outra entidade
  usa o proxy normal.
- **Proxy transparente**: Para os outros 3 modos + create genérico, o comando monta
  um `CliCommandRequest` equivalente para `ontobdc context` (com `--container`
  já preenchido pelo `container_id` resolvido) e chama `ContextEntityCommand.run()`
  diretamente.
- **Atenção / `check()`**:
  - Modos 1 e 2 são globais (pulam `ProjectIdStrategy`).
  - Modos 3 e 4 **exigem** que `ProjectIdStrategy` retorne `project_id`,
    `container_id`, `container_path` — todos três não-vazios.

### 4.2. `context_help` — ajuda do domínio `context`

- **Formato**: `infobim context --help` / `-h`
- **Descrição na resposta**: "Operate OntoBDC context entities through InfoBIM Projects."

---

## 5 · Componente `view` (Surface do Projeto)

### 5.1. `view_project` — gerar Surface HTML e abrir navegador

- **ID metadata**: `view_project`
- **Classe**: `ViewProjectCommand`
- **Arquivo**: [project.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/infobim/view/plugin/command/project.py)
- **State machine**: `InfoBIMSurfaceGenerationStateTransitionHandler`
- **Formato de rota**:
  ```bash
  infobim view [--project-id <GlobalId>|--project <selector>] \
               [--type standard] \
               [--representation html] \
               [--language en|pt]
  ```
- **Uso usuário mais comum** (dentro do diretório do Projeto):
  ```bash
  infobim view
  ```
- **Uso explícito de outro projeto**:
  ```bash
  infobim view --project-id 2O2Fr$t4X7Zf8NOew3FNld --language pt
  ```
- **O que o usuário percebe (pipeline completo)**:
  1.  Resolve `project_id`, `project_path` (dentro do diretório ou via flag).
  2.  Carrega a **presentation do InfoBIM** (`InfoBIMProjectPresentationRepository`)
      que extrai, a partir das dataset facades, a lista de classes (`classes`) e
      a contagem de elementos (`element_count`).
  3.  **Reseta artefatos antigos**: apaga o `index.html` da Surface anterior e o
      diretório de ETL `data_gathered/` (capacidade `DataGatheredCapability`),
      para que a geração seja idempotente.
  4.  Injeta **3 componentes JS InfoBIM-específicos** no contexto
      (`surface_component_scripts` via `InfoBIMComponentSourceAdapter().scripts()`):
      - `onto-infobim-project-tile.js` (tile do projeto)
      - `onto-infobim-ifc-model-tile.js` (tile de modelo IFC navegável)
      - `onto-infobim-ifc-work-schedule-tile.js` (tile de cronograma)
  5.  Roda a state machine `InfoBIMSurfaceGenerationStateTransitionHandler`
      (monta o HTML do OntoBDC com os componentes extras injetados).
  6.  Verifica que `index.html` foi gerado.
  7.  **Abre o navegador padrão** com `webbrowser.open(index_uri, new=2)`.
  8.  Devolve uma resposta com **todos os metadados úteis de debug**:
      `project_id`, `project_path`, `container_id`, `view_type`,
      `representation`, `language`, `index_path`, `index_uri`,
      `browser_opened` (bool), `runtime_error` (se falhou ao abrir browser),
      `ifc_class_count`, `ifc_element_count`.
- **Guardas / `check()`**:
  - Valida que `--project-id` e `--project` **não são passados simultaneamente**.
  - Suporta apenas `--type standard` e `--representation html` no momento
    (outros valores levantam `CliCommandArgumentException`).
  - `--language` tem default `en`; qualquer string é aceita.
  - Dois erros de usuário distintos:
    - Se flag foi passada mas não bate com nada registrado:
      `"No InfoBIM Project matches the given --project-id/--project selector..."`
    - Se estiver em diretório aleatório sem flag:
      `"No IfcProject found in this directory. Run infobim view from inside an InfoBIM Project directory..."`
- **Observação arquitetural**: A geração da Surface é **totalmente delegada** à
  pipeline central do OntoBDC; o que o InfoBIM faz é:
  (a) resolver o contexto de Projeto e
  (b) "injetar" seus 3 plugins de tile JS próprios antes de rodar a pipeline.

### 5.2. `view_help` — ajuda do domínio `view`

- **Formato**: `infobim view --help`
- **Descrição na resposta**:
  "Present an InfoBIM Project as its IfcProject and one navigable distributed IFC Model domain."

---

## 6 · Apêndice A — tabela compacta (12 comandos de operação)

| Intenção do usuário | Comando curto | Rota recomendada |
|---|---|---|
| Inicializar workspace InfoBIM | `init` | `infobim init` |
| Ver versão do InfoBIM instalada | `--version` | `infobim -v` |
| Ver ajuda geral / todos comandos | `welcome` | `infobim` |
| Criar novo Projeto vazio | `project --create` | `infobim project --create ~/obra-a` |
| Listar Projetos InfoBIM cadastrados | `project --list` | `infobim project --list` |
| Anexar Projeto importado de HD externo | `project --project-path ... --attach` | `infobim project --project-path /mnt/ext/foo --attach` |
| Re-extrair / reprocessar Projeto | `project --update` (cwd ou flag) | `infobim project --update` |
| Remover Projeto do índice (por GlobalId) | `project --delete <id>` | `infobim project --delete 2O2Fr$t4X...` |
| Inventariar classes IFC presentes | `ifc ... --class --all` | `infobim ifc --project-id <id> --class --all` |
| Listar elementos de UMA classe IFC | `ifc ... --class <c> --all` | `infobim ifc --project-id <id> --class IfcWall --all` |
| Detalhar UM elemento (GlobalId) | `ifc --element` | `infobim ifc --project-id <id> --element <elem_id>` |
| Trabalhar com entidades (catálogo / lookup / instâncias / criar) | `context --entity` | `infobim context --entity --all` |
| Criar **entidade cronograma** (InfoBIM-specific service) | `context --create X --entity IfcWorkSchedule` | `infobim context --create "Crono A" --entity IfcWorkSchedule --project-id <id>` |
| Abrir Surface HTML do Projeto no navegador | `view` (com default total) | `infobim view` |

---

## 7 · Apêndice B — comandos LEGACY (`src/old/`) — NÃO USAR

> A pasta `infobim/src/old/` contém a implementação anterior (monolítica) dos
> mesmos conceitos. **Ela não é mais descoberta pelo `CommandLoader` atual**
> (uma vez que o loader só procura módulos em `src/infobim/`). Essa listagem
> existe apenas para auditoria / conhecimento histórico. **Não crie automações
> em cima deles**.

| Arquivo legado | Classe | `METADATA.id` | Descrição breve |
|---|---|---|---|
| [old/cli/plugin/command/base.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/cli/plugin/command/base.py) | `CliBaseCommand` | `base` | CLI base legada da engine pré-OntoBDC |
| [old/cli/plugin/command/init.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/cli/plugin/command/init.py) | `CliInitCommand` | `init` | Inicializador legado (herdava `OntoBDCCliInitCommand` antigo) |
| [old/project/plugin/command/base.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/base.py) | `ProjectBaseCommand` | `base` | Base legada do container Projeto (pós-engine) |
| [old/project/plugin/command/create.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/create.py) | `StorageCreateCommand` | `proj_create` | Criação legada (monolítica, YAML `standard_container_create.yaml`) |
| [old/project/plugin/command/import.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/import.py) | `ProjectImportCommand` | `import` | Import legado de IFC no container (estados: `extracted → identified → parsed → instantiated...`) |
| [old/project/plugin/command/detail.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/detail.py) | `ProjectDetailCommand` | `detail` | Detalhe legado de projeto |
| [old/project/plugin/command/update.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/update.py) | `ProjectUpdateCommand` | `update` | Atualização legada de container |
| [old/project/plugin/command/create_element.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/create_element.py) | `ProjectCreateElementCommand` | `project_create_element` | Criação de elemento IFC legada (via strategy pattern) |
| [old/project/plugin/command/locate.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/project/plugin/command/locate.py) | `ProjectLocateElementCommand` | `proj_locate_element` | Localização (bounding-box) legada de elemento |
| [old/context/plugin/command/learning.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/context/plugin/command/learning.py) | `ContextLearnFromIfcElementCommand` | `learn_from_ifc_element` | Aprendizado legado de perfil de entidade a partir de elemento IFC selecionado |
| [old/view/plugin/command/project.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/view/plugin/command/project.py) | `ViewProjectCommand` (legado) | `project` | Surface legada (dashboard template `project_dashboard.html.j2`) |
| [old/view/plugin/command/element.py](file:///Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/infobim/src/old/view/plugin/command/element.py) | `ViewElementCommand` | `element` | Surface legada de elemento individual (anotações + workstream 5W2H) |
