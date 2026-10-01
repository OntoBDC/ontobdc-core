# Regras específicas — Trae

## Branch obrigatória
O Trae deve trabalhar **exclusivamente** na branch `trae/noah-release`.

É proibido ao Trae criar commits, fazer push, alterar refs ou escrever
diretamente em `noah-release`, `master`, qualquer branch de release ou qualquer
outra branch diferente de `trae/noah-release`.

Se `trae/noah-release` ainda não existir, ela deve ser criada a partir de
`noah-release` antes de qualquer alteração.

Todo o trabalho deve permanecer em `trae/noah-release` até validação explícita
do usuário. A conclusão técnica da tarefa **não** autoriza a abertura de Pull
Request.

Somente depois de o usuário validar explicitamente o trabalho, o Trae deve
abrir uma Pull Request de `trae/noah-release` para `noah-release`.

O Trae não deve fazer merge da Pull Request nem escrever diretamente em
`noah-release`, salvo instrução explícita posterior do usuário.

## Commit de todas as alterações pendentes
Todo commit realizado pelo Trae deve abranger **TUDO** o que estiver pendente
no repositório no momento do commit, incluindo alterações preparadas, não
preparadas e arquivos não rastreados. É proibido fazer commit parcial, excluir
arquivos ou hunks pendentes ou deixar qualquer alteração para um commit
posterior.
