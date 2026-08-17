# AGENTS.md — Regras Obrigatórias para Trabalho Neste Repositório

> **Aplicabilidade irrestrita.** Toda e qualquer alteração, análise, investigação,
> proposta de código ou refatoração feita por agentes de LLM neste repositório
> **deve cumprir TODAS as regras abaixo, sem exceção e sem negociação.**
>
> Qualquer resultado que viole pelo menos uma regra abaixo é automaticamente
> considerado inválido e deve ser descartado sem necessidade de justificativa
> adicional do usuário.

---

## Regras do LLM (ordem alfanumérica e obrigatória, 1–16)

### 1. Mensagens de commit semânticas e em INGLÊS
Todas as mensagens de commit geradas devem seguir o padrão de Commits Semânticos (prefixo `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `perf:`, `test:`, *etc.*) e ser obrigatoriamente escritas em **INGLÊS**.

### 2. DIRETÓRIO RESTRITO — NUNCA TOCAR
Nunca, sob nenhuma hipótese, **alterar, editar, ler ou interagir** com os arquivos do diretório:

```
/Users/eliasmpjunior/infobim/deploy/ontobdc-stack/core
```

Qualquer menção ou sugestão de alteração neste diretório é proibida.

### 3. Sem gambiarra, workaround, marreta ou solução paliativa
Não propor nem implementar gambiarra, workaround, marreta, "solução rápida" ou
solução paliativa. **Priorizar sempre a causa raiz.** Casos que precisam de
mitigação temporária por algum motivo explicitamente validado NÃO existem —
resolver a causa raiz ou não tocar no código.

### 4. Seguir o padrão existente
Respeitar a arquitetura, os contratos, as convenções de nomenclatura, ordem de
imports, estilo de código e os padrões já adotados no projeto. Não introduzir
novos estilos ou novos padrões paralelos se já houver um modo consensual de
fazer a mesma coisa em outro ponto do código.

### 5. Não tocar em arquivos não relacionados
Limitar **qualquer** análise ou alteração apenas aos arquivos estritamente
necessários para a tarefa solicitada. Não fazer "limpeza paralela", refatoração
acidental, organização de imports não solicitada ou ajustes em arquivos
vizinhos sem pedido explícito.

### 6. Sem fallback não solicitado
Não adicionar fallback, plano B, tratamento alternativo, caminho de degradação
ou comportamento "modo compatibilidade" a menos que isso seja pedido
**explicitamente** pelo usuário. O caminho feliz é obrigatório; o caminho
triste é a exception original propagada inalterada.

### 7. Seguir a referência indicada pelo usuário
Quando o usuário apontar **explicitamente** um arquivo, símbolo, propriedade,
linha, trecho ou caminho como fonte para resolver a tarefa, essa referência
deve ser tratada como **autoritativa** e usada primeiro. Não explorar
alternativas, não procurar outros caminhos, não inferir fontes concorrentes e
não expandir o escopo sem necessidade. Se a referência fornecida for
suficiente, fazer apenas a alteração mínima necessária e parar.

### 8. Não investigar além do necessário
Em tarefas pontuais, não realizar buscas amplas, leituras paralelas ou
exploração arquitetural se o usuário já tiver indicado o local exato da
mudança. Diagnóstico adicional só é permitido quando a referência informada
for insuficiente ou inconsistente com o comportamento real.

### 9. Padrões de código (obrigatório — SOLID, KISS, DRY, Clean Arch, Clean Code)
Seguir sem exceção os princípios:
- **S.O.L.I.D.** — responsabilidade única, aberto/fechado, substituição de Liskov,
  segregação de interface, inversão de dependência.
- **KISS** — keep it simple, stupid.
- **DRY** — don't repeat yourself.
- **Clean Architecture** — camadas com dependência apontando sempre para dentro;
  entidades centrais não importam adaptadores ou entrypoints.
- **Clean Code** — nomes significativos, funções pequenas, sem comentários
  desnecessários, sem side-effects ocultos.

### 10. Tipagem explícita (obrigatória)
**SEMPRE** tipar as variáveis locais, os atributos de classe, os parâmetros de
função/método e os retornos. Preferir tipagem explícita (`x: int = 5`) à
inferência (`x = 5`) quando isso aumentar clareza ou evitar ambiguidade. O
único caso em que a inferência é aceitável é quando o lado direito já é
explícito por si só (ex: `x = ListaTipada()` já retorna `ListaTipada`).

### 11. Coleções tipadas (obrigatória)
**Não usar** `list`, `dict`, `set` ou `tuple` nus (sem parâmetros de tipo).
Usar **sempre** `List[T]`, `Dict[K, V]`, `Set[T]` e `Tuple[...]` do módulo
`typing`. Pode usar `Any` quando necessário, mas justificar mentalmente o
motivo e preferir um tipo concreto sempre que possível.

### 12. Imports apenas no início do arquivo (obrigatória)
**NUNCA** colocar `import` no meio do código. E, se encontrar alguma ocorrência
como resultado de uma tarefa, mover para o cabeçalho. Todos os imports devem
ficar **exclusivamente no início do arquivo**, seguindo a ordem e o
agrupamento já adotados no projeto (ver Regra 15).

> **Exceção ÚNICA e autorregulada**: `import` lazy dentro de método/função em
> módulos de camada mais baixa (ex: `shared.facade.*`) quando importar no
> topo causaria **importação circular de ciclo fechado** e não há outra saída
> arquitetural. Essa exceção exige `__getattr__` de módulo (PEP 562) ou
> `try/except` com guarda robusta e não pode ser usada para "facilitar"
> imports sem causa raiz.

### 13. Reutilizar adapters centrais do projeto (obrigatório)
Antes de resolver manualmente caminhos de arquivos, ontologias, namespaces,
diretórios raiz, configuração ou cache, **verificar e reutilizar primeiro os
adapters centrais já existentes no projeto**, especialmente:

- módulo `ontobdc.shared.adapter.ontology`
- helpers centrais: `OntologyConfigAdapter`, `get_ontology_by_prefix`,
  `get_ontology_path`, `get_ontology_content`
- `ConfigDataAdapter`

É **proibido** ignorar esses pontos centrais e inventar resolução paralela,
hardcode local, busca manual ad-hoc ou acesso direto quando já existir adapter
oficial para isso.

### 14. Proibido path absoluto como solução de código ou regra
Não usar path absoluto fixo em código, configuração, documentação operacional
ou regras de trabalho quando houver alternativa portátil baseada em adapters,
configuração do projeto, imports de módulo, caminhos relativos controlados ou
resolução pelo ambiente. Path absoluto só pode aparecer quando o usuário pedir
**explicitamente** ou quando for indispensável para descrever um arquivo
específico apontado pelo próprio usuário.

### 15. Exigências de Boas Práticas (PEP 8)
1.  **Ordem.** Manter os imports no topo do arquivo.
2.  **Agrupamento.** Seguir a ordem:
    1.  Biblioteca Padrão do Python
    2.  Bibliotecas de terceiros
    3.  Imports locais (módulos do próprio projeto)
3.  **Evitar `from modulo import *`.** Isso polui o namespace e torna difícil
    saber de onde vieram as funções. Preferir imports explícitos:
    `from math import sqrt` em vez de `from math import *`.
4.  **Imports absolutos vs relativos.** Preferir imports absolutos (ex:
    `from ontobdc.shared.utils import helper`) em vez de relativos (ex:
    `from ..utils import helper`), pois eles são mais claros e robustos.

### 16. Proibido deixar funções "soltas" (top-level free functions)
**Não adicionar, não manter, não introduzir funções de nível de módulo (free
functions) espalhadas por arquivos.** Toda lógica que em outra linguagem iria
para uma função utilitária avulsa deve, **neste projeto**, ser encapsulada em
pelo menos um dos mecanismos abaixo (em ordem de preferência):

1.  **Método estático (`@staticmethod`) ou método de classe (`@classmethod`)**
    em uma classe de namespace/helper dedicada.
2.  **Classe concreta com responsabilidade única (SRP)** que possui a lógica
    como método de instância, mesmo que a classe não carregue estado
    persistente.
3.  **Módulo dedicado** em pacote apropriado (não em arquivo de entrada,
    não em arquivo que já contém classes de domínio).

**O que é proibido explicitamente:**

- Funções `def _nome_aleatorio(args) -> Tipo:` declaradas diretamente no corpo
  do módulo, fora de qualquer classe, em arquivos que também contêm classes de
  domínio, ports, adapters ou entry-points.
- Helper functions jogadas no meio de `cli/__init__.py`,
  `shared/adapter/*.py`, `storage/adapter/*.py`, `view/adapter/*.py`,
  `context/adapter/*.py` ou qualquer outro arquivo que **não seja** um módulo
  utilitário de propósito único.
- Funções soltas que só existem "porque foi mais fácil escrever" do que
  encapsular.

**O que é exceção (muito restrita):**

- Entry-points de script do tipo `if __name__ == "__main__":` com uma função
  `main()` — desde que `main()` seja a **única** função do arquivo e o arquivo
  exista só para ser executado (não seja importado por outros módulos).
- Funções `__getattr__`, `__dir__` ou outros hooks de módulo da PEP 562
  (exclusivamente para lazy-loading de exports, como em
  `shared/facade/adapter/logger.py`).
