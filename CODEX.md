# Regras específicas — Codex

## Branch obrigatória
O Codex deve trabalhar **exclusivamente** na branch `codex/noah-release`.

É proibido ao Codex criar commits, fazer push, alterar refs ou escrever
diretamente em `noah-release`, `master`, qualquer branch de release ou qualquer
outra branch diferente de `codex/noah-release`.

Se `codex/noah-release` ainda não existir, ela deve ser criada a partir de
`noah-release` antes de qualquer alteração.

Todo o trabalho deve permanecer em `codex/noah-release` até validação explícita
do usuário. A conclusão técnica da tarefa **não** autoriza a abertura de Pull
Request.

Somente depois de o usuário validar explicitamente o trabalho, o Codex deve
abrir uma Pull Request de `codex/noah-release` para `noah-release`.

Toda Pull Request aberta pelo Codex deve ser criada diretamente como
**ready for review**. É proibido criar Pull Requests como draft ou converter
uma Pull Request para draft durante o fluxo de publicação.

O Codex não deve fazer merge da Pull Request nem escrever diretamente em
`noah-release`, salvo instrução explícita posterior do usuário.

## Commit de todas as alterações pendentes
Todo commit realizado pelo Codex deve abranger **TUDO** o que estiver pendente
no repositório no momento do commit, incluindo alterações preparadas, não
preparadas e arquivos não rastreados. É proibido fazer commit parcial, excluir
arquivos ou hunks pendentes ou deixar qualquer alteração para um commit
posterior.

## Comando para retomada literal de classes
Quando o usuário disser **“retome essas classes”** e listar uma ou mais classes,
o Codex deve procurar cada classe exclusivamente em um destes diretórios:

- `/Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/lost-release/core`
- `/Users/eliasmpjunior/Brasidata/07_Engenharia_e_Tecnologia/06_Solucoes_Reutilizaveis/OntoBDC/lost-release/ontobdc-view`

Para cada classe listada, o Codex deve copiar **apenas a classe, ipsis litteris**,
para o mesmo caminho relativo e o mesmo arquivo no projeto correspondente. É
proibido fazer qualquer outra alteração, incluindo adaptar, refatorar, formatar,
corrigir, complementar imports, copiar outros símbolos, criar ou alterar testes
ou modificar qualquer outro arquivo.
