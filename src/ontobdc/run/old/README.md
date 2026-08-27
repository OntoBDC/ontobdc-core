Encontrei. E encontrei um ponto de resgate muito bom: o **merge do `refactor/run`, PR #38, em 8 de junho de 2026**, commit `2c9a5776a7bbcb05658fcb08bce33be7f79e7f7c`. Nesse snapshot o `ontobdc run` está inteiro, já na arquitetura de state machine + intent resolution + planning + parameter filling + execução de capability.

E tem um detalhe importante: eu **não resgataria só `base.py`**. O `run` era praticamente um subsistema.

### O comando propriamente dito

O entry point lógico era:

```text
ontobdc run
```

e o `RunBaseCommand` declarava:

```python
id="base"
logical_component="run"
```

com `accepts: []`. Ou seja: o comando base era efetivamente `ontobdc run`; o restante entrava como contexto/argumentos para o runtime, não como um subcomando obrigatório.

O help possuía apenas o comando adicional explícito:

```text
ontobdc run --help
ontobdc run -h
```

e o próprio help carregava dinamicamente os comandos do componente `run` por `CommandLoader('run')`.

Historicamente houve também uma fase anterior com coisas como `--id`, seleção interativa e filtragem por argumentos. Isso foi evoluindo e acabou desembocando nesse runtime semântico mais sofisticado de junho.

---

## O que o `ontobdc run` fazia em junho

O fluxo final era aproximadamente:

```text
ontobdc run
    │
    ▼
CLI Context
    │
    ▼
Intent State Machine
    │
    ├── resolve idioma
    ├── obter intenção
    ├── canonicalizar
    ├── parsear
    ├── avaliar confiança
    ├── validar intenção
    ├── planejar capabilities
    ├── resolver parâmetros
    │
    ▼
Capability target resolvida
    │
    ▼
CapabilityExecutor.execute(...)
```

Isso não é inferência minha; é exatamente o comportamento do `RunBaseCommand`: ele cria `SismicIntentTransitionHandlerAdapter`, abre o statechart, executa as transições até um estado final, pega `handler.target_capability`, pega o contexto final e chama:

```python
CapabilityExecutor.execute(capability, final_context)
```

Portanto, conceitualmente, **`run` não era “execute esta capability”**. Ele havia virado:

> **descubra o que precisa ser feito → determine se é executável → produza o plano → preencha os inputs → execute a capability final.**

Isso é bem mais interessante para trazer de volta.

---

# A árvore inteira que precisa ser olhada

No snapshot `2c9a577...`, o pacote era este:

```text
src/ontobdc/run/
│
├── adapter/
│   ├── evaluator.py
│   ├── machine.py
│   ├── repository.py
│   └── spacy.py
│
├── domain/
│   ├── exception/
│   │   ├── __init__.py
│   │   └── intent.py
│   │
│   ├── machine/
│   │   ├── capability_intent_resolution.yaml
│   │   ├── lifecycle.py
│   │   └── response.py
│   │
│   └── port/
│       ├── dag.py
│       ├── intent.py
│       └── machine.py
│
└── plugin/
    ├── __init__.py
    │
    ├── capability/
    │   ├── __init__.py
    │   ├── resolution_from_low_confidence.py
    │   ├── resolution_to_canonical.py
    │   ├── resolution_to_filled.py
    │   ├── resolution_to_intended.py
    │   ├── resolution_to_language_defined.py
    │   ├── resolution_to_parsed.py
    │   ├── resolution_to_planned.py
    │   └── resolution_to_validated.py
    │
    ├── check/
    │   └── has_valid_context/
    │       ├── check.py
    │       ├── hotfix.py
    │       └── init.sh
    │
    ├── command/
    │   ├── base.py
    │   └── help.py
    │
    └── resolver/
        └── parsed_intent.py
```

Essa árvore está literalmente no Git tree daquele commit.

Então, para resgatar o bicho inteiro, são **30 arquivos aproximadamente**, não dois.

---

# A máquina de estados

Essa é provavelmente a parte mais valiosa para a versão nova.

Os estados eram:

```text
UNDEFINED
    ↓
EMPTY
    ↓
LANGUAGE_DEFINED
    ↓
INTENDED
    ↓
CANONICAL
    ↓
PARSED
    ├───────────────┐
    ↓               ↓
VALIDATED      LOW_CONFIDENCE
    ↑               │
    └───────────────┘
    ↓
PLANNED
    ↓
FILLED
```

com uma saída alternativa:

```text
VALIDATED
    ↓
UNREACHABLE
```

Os nomes oficiais eram:

```python
UNDEFINED
EMPTY
LANGUAGE_DEFINED
INTENDED
PARSED
CANONICAL
LOW_CONFIDENCE
VALIDATED
PLANNED
FILLED
UNREACHABLE
```

E o YAML formaliza as guards e actions. Por exemplo, depois de `PARSED`:

```text
score suficiente
    → VALIDATED

score insuficiente
    → LOW_CONFIDENCE
```

Depois de `VALIDATED`:

```text
plano solucionável
    → PLANNED

plano insolucionável
    → UNREACHABLE
```

e:

```text
PLANNED + execution_plan_is_valid()
    → FILLED
```

Isso dá para trazer quase conceitualmente intacto, mesmo que a implementação atual de state machine tenha mudado.

---

# Como ele ligava estados a capabilities

Aqui está uma das peças que eu definitivamente preservaria.

O `machine.py` não tinha um enorme `if/elif` chamando cada etapa. Ele construía semanticamente o ID da capability:

```python
target_id = (
    "org.ontobdc.run.plugin.capability.resolution.target."
    + state_name
)
```

e então procurava essa capability no:

```python
CapabilityLoader().get_all("capability")
```

Ao encontrá-la:

```python
CapabilityExecutor.execute(capability, self._context)
```

e recebia de volta o novo:

```python
cli_context
```

Ou seja:

```text
state transition
       │
       ▼
semantic capability ID
       │
       ▼
CapabilityLoader
       │
       ▼
CapabilityExecutor
       │
       ▼
novo contexto
```

Muito OntoBDC. Nada de dispatcher com 47 `ifs`. Bonito até hoje.

---

# As capabilities internas do `run`

Correspondendo aos estados, havia:

```text
resolution_to_language_defined
resolution_to_intended
resolution_to_canonical
resolution_to_parsed
resolution_from_low_confidence
resolution_to_validated
resolution_to_planned
resolution_to_filled
```

A nomenclatura usada pelo handler era:

```text
org.ontobdc.run.plugin.capability.resolution.target.<state>
```

ou, para transições que saíam de uma condição:

```text
org.ontobdc.run.plugin.capability.resolution.from.<state>
```

Isso quer dizer que a própria resolução de intenção já era modelada como **capabilities executadas pelo mesmo runtime de capabilities**.

Esse detalhe é arquiteturalmente importante.

---

# Planning / DAG

O `run` não pulava de “achei a capability” para “executa”.

O handler tinha:

```python
execution_plan_is_valid()
execution_plan_is_unreachable()
```

e ambos passavam por:

```python
DagParametersEvaluator(self._context).evaluate()
```

O comentário no código é particularmente claro: um plano válido é aquele em que a target capability está definida e os parâmetros obrigatórios podem ser satisfeitos **diretamente pelo contexto ou por support capabilities disponíveis**.

Isso conecta diretamente o `run` à ideia de:

```text
target capability
      │
      ├── input A ← contexto
      │
      ├── input B ← contexto
      │
      └── input C ← capability auxiliar
                         │
                         └── input D ...
```

Portanto o resgate precisa considerar também a infraestrutura compartilhada de DAG/capabilities, e não simplesmente copiar `src/ontobdc/run`.

---

# Dependências externas ao diretório `run`

No mesmo snapshot, ele dependia fortemente de:

```text
src/ontobdc/shared/
├── adapter/
│   ├── context.py
│   ├── machine.py
│   ├── ontology.py
│   └── plugin.py
│
├── domain/port/
│   ├── capability.py
│   ├── context.py
│   ├── machine.py
│   ├── param.py
│   ├── repository.py
│   └── resolver.py
│
└── domain/resource/
    ├── capability.py
    ├── context.py
    └── param.py
```

e da infraestrutura CLI:

```text
src/ontobdc/cli/
├── adapter/command.py
├── domain/port/command.py
└── domain/resource/command.py
```

Então eu dividiria o resgate em duas categorias:

**RUN-specific**

```text
intent resolution
statechart
intent parser/scoring
planning orchestration
low-confidence handling
context filling
command shell
```

**infraestrutura que provavelmente já sobreviveu na versão nova**

```text
CapabilityLoader
CapabilityExecutor
CliContext
Parameter strategies
CommandLoader
CommandResponse
state machine abstractions
plugin discovery
```

Aqui é onde não queremos cometer o crime arqueológico clássico: ressuscitar junto com o faraó todos os criados que já têm emprego novo.

---

# Evolução do comando — o que existiu antes dessa versão

Também achei a linha evolutiva. Isso ajuda porque talvez você queira recuperar alguns comportamentos antigos sem recuperar a implementação antiga.

Em **1º de março**, `run --help` listava capabilities/actions e seus inputs em tabela rica. Depois passou a exibir tipo dos inputs e quais eram obrigatórios.

Em **4 de março**, entrou explicitamente:

```text
ontobdc run --id <capability-id>
```

para execução direta sem ambiguidade interativa.

Também havia o comportamento:

```text
ontobdc run
```

→ seleção interativa.

E argumentos de contexto podiam restringir quais capabilities eram aplicáveis.

Depois:

```text
.__ontobdc__/config.yaml
```

passou a controlar packages de capabilities e, depois, custom parameter strategies.

Houve inclusive:

```text
--text-file
    ↓
TextFileStrategy
    ↓
raw_text_path
```

em maio.

E finalmente, entre fim de maio e começo de junho, o `run` deixou de ser fundamentalmente um “capability picker” e virou o **intent-resolution runtime** que estamos vendo aqui.

Então eu considero que existem **duas gerações de `ontobdc run`**:

```text
GERAÇÃO 1
CLI → filtros/contexto → lista capability → escolhe → executa

GERAÇÃO 2
CLI/raw intent
   → semantic intent resolution
   → capability discovery
   → execution planning
   → parameter resolution
   → capability execution
```

A que está no PR #38 é a **segunda** e, para trazer para o OntoBDC atual, é nela que eu me basearia.

---

## O ponto exato para escavar

Eu usaria como referência principal:

```text
Repository:
EliasMPJunior/ontobdc-wip

Commit:
2c9a5776a7bbcb05658fcb08bce33be7f79e7f7c

Mensagem:
Merge pull request #38 from EliasMPJunior/refactor/run
Refactor/run

Data:
2026-06-08
```

Esse é, até agora, o **snapshot mais coerente e completo que encontrei do `run` já refatorado**.

E tem ainda o PR anterior:

```text
#35 feat/run_with_contet
```

mergeado em **28 de maio**, que é útil para investigar especificamente a evolução do preenchimento de contexto.

Eu não começaria copiando código ainda. O próximo passo que faz sentido é eu montar para você um **mapa de resgate arquivo por arquivo**, comparando esse `run` de junho com o `ontobdc-core` atual e classificando cada peça em:

```text
RECUPERAR
ADAPTAR
JÁ EXISTE
OBSOLETO
```

Aí a gente sabe exatamente **o que trazer de volta**, sem despejar um cadáver de junho dentro da v0.19.