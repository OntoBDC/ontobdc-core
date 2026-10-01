# Regras específicas — ChatGPT

## Branch obrigatória
O ChatGPT deve trabalhar **exclusivamente** na branch `chatgpt/noah-release`.

É proibido ao ChatGPT criar commits, fazer push, alterar refs ou escrever
diretamente em `noah-release`, `master`, qualquer branch de release ou qualquer
outra branch diferente de `chatgpt/noah-release`.

Se `chatgpt/noah-release` ainda não existir, ela deve ser criada a partir de
`noah-release` antes de qualquer alteração.

Todo o trabalho deve permanecer em `chatgpt/noah-release` até validação explícita
do usuário. A conclusão técnica da tarefa **não** autoriza a abertura de Pull
Request.

Somente depois de o usuário validar explicitamente o trabalho, o ChatGPT deve
abrir uma Pull Request de `chatgpt/noah-release` para `noah-release`.

O ChatGPT não deve fazer merge da Pull Request nem escrever diretamente em
`noah-release`, salvo instrução explícita posterior do usuário.

## Revisão de Pull Requests
Ao revisar Pull Requests, o ChatGPT pode inspecionar metadata, diff/patch,
comentários, threads, checks e workflows, produzir análise técnica e apontar
problemas encontrados.

Toda revisão deve ser feita **rigorosamente** contra os critérios arquiteturais,
de qualidade e de documentação vigentes do projeto. O ChatGPT deve, no mínimo:

- conferir se as alterações respeitam a arquitetura estabelecida do OntoBDC,
  incluindo separação de responsabilidades, camadas, portas/adapters, plugins,
  capabilities, machines/FSMs, statecharts, convenções de carregamento e demais
  padrões arquiteturais aplicáveis ao trecho alterado;
- conferir rigorosamente os linters, formatadores, validadores estáticos e demais
  regras de qualidade configuradas no repositório, não tratando como aceitável
  código que viole essas regras apenas por aparentemente funcionar;
- conferir a implementação contra a documentação correspondente em
  `ontobdc-doc`, usando a documentação como fonte normativa para contratos,
  comportamento esperado, terminologia, arquitetura e convenções documentadas;
- verificar se testes e checks relevantes cobrem adequadamente a mudança e se o
  comportamento implementado corresponde ao contrato arquitetural e documental,
  e não apenas ao resultado imediato do teste.

Quando encontrar problemas que justifiquem correção antes da integração, o
ChatGPT **deve solicitar mudanças (`REQUEST_CHANGES`)**, descrevendo de forma
objetiva e tecnicamente acionável o que precisa ser corrigido. A autorização
para revisar uma Pull Request inclui essa ação de revisão.

Todo comentário técnico e todo `REQUEST_CHANGES` deve apresentar a
**fundamentação da exigência**. Não basta afirmar que algo está errado ou pedir
uma alteração por preferência. O ChatGPT deve indicar, conforme o caso, a regra
arquitetural violada, a regra de linter/qualidade aplicável, o contrato ou trecho
correspondente de `ontobdc-doc`, a convenção já estabelecida no código, ou outra
evidência técnica concreta que sustente a exigência. Quando possível, deve
apontar o arquivo, módulo, símbolo, regra, documento ou seção que serve de base
para o comentário.

A solicitação para **revisar** uma Pull Request **não autoriza** o ChatGPT a:

- aprovar a Pull Request (`APPROVE`);
- fazer merge;
- habilitar auto-merge;
- fechar ou reabrir a Pull Request;
- alterar branch base, reviewers, labels ou qualquer outro estado da Pull Request
  que não seja a submissão de `REQUEST_CHANGES` necessária à própria revisão.

Essas ações exigem autorização explícita e específica do usuário. A ausência de
problemas técnicos, checks verdes ou uma conclusão de que a Pull Request está
correta **não constitui autorização para aprovação ou merge**.

Portanto, durante uma revisão, o ChatGPT pode ler, analisar, comentar e submeter
`REQUEST_CHANGES` quando houver problemas. Se a Pull Request estiver correta,
deve apenas informar ao usuário; não deve aprová-la nem fazer merge sem ordem
explícita.

## Sincronização obrigatória quando operando pelo conector GitHub
Quando estiver trabalhando por meio do conector GitHub do ChatGPT, não existe
shell local nem execução literal de `git pull`. Essa limitação de ferramenta
**não elimina nem enfraquece** a obrigação definida no `AGENTS.md` de obter o
estado remoto mais recente de `origin/noah-release` antes de cada tarefa.

Antes de iniciar qualquer tarefa, o ChatGPT deve consultar novamente o HEAD
remoto atual de `noah-release`, comparar esse estado com
`chatgpt/noah-release` e reproduzir, por meio das operações disponíveis na API
do GitHub, o efeito semântico de atualizar `origin/noah-release` e fazer merge
de `noah-release` na sua branch de trabalho. A sincronização deve preservar o
histórico existente da branch do ChatGPT e nunca pode descartar commits por
force reset, sobrescrita de ref ou expediente equivalente.

O ChatGPT nunca deve afirmar que executou literalmente `git pull` quando tiver
usado a API do GitHub. Deve distinguir claramente a execução via conector da
execução via shell, mantendo porém a mesma garantia exigida pela regra: a tarefa
só pode começar depois de `chatgpt/noah-release` incorporar o estado remoto mais
recente de `noah-release`.

Se a API disponível não permitir realizar o merge com segurança, se houver
conflito que não possa ser resolvido sem descartar trabalho, ou se não for
possível confirmar o estado remoto atual, o ChatGPT deve interromper a tarefa e
informar o impedimento ao usuário. É proibido contornar essa limitação começando
a alteração sobre uma branch desatualizada.
