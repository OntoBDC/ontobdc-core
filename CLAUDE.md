# Regras específicas — Claude

## Branch obrigatória
O Claude deve trabalhar **exclusivamente** na branch `claude/noah-release`.

É proibido ao Claude criar commits, fazer push, alterar refs ou escrever
diretamente em `noah-release`, `master`, qualquer branch de release ou qualquer
outra branch diferente de `claude/noah-release`.

Se `claude/noah-release` ainda não existir, ela deve ser criada a partir de
`noah-release` antes de qualquer alteração.

Todo o trabalho deve permanecer em `claude/noah-release` até validação explícita
do usuário. A conclusão técnica da tarefa **não** autoriza a abertura de Pull
Request.

Somente depois de o usuário validar explicitamente o trabalho, o Claude deve
abrir uma Pull Request de `claude/noah-release` para `noah-release`.

O Claude não deve fazer merge da Pull Request nem escrever diretamente em
`noah-release`, salvo instrução explícita posterior do usuário.

## Idioma

Explicações longas devem ser escritas **sempre em inglês**: análise, raciocínio,
descrição do que foi feito, resposta a pergunta técnica, corpo de issue e de
Pull Request, mensagem de commit, docstring e comentário de código.

O português fica reservado à conversa curta — confirmar, perguntar, avisar em
uma ou duas frases. Assim que a resposta passa disso, ela é em inglês.

## Comando: "retome essas classes"

Quando o usuário disser **"retome essas classes"** seguido de uma lista de
classes, o Claude deve, para cada classe listada:

1. Ir a `lost-release/core/` ou `lost-release/ontobdc-view/` e localizar a classe.
2. Copiar **apenas** a classe, *ipsis litteris*, no mesmo path e no mesmo arquivo.
3. Não fazer mais nada além disso: sem adaptar imports, sem refatorar, sem
   corrigir, sem tocar em outra classe ou arquivo, sem análise, sem sugestão.

## Relatório de tarefa

Ao concluir uma tarefa, o Claude deve reportá-la ao usuário de forma
**resumida** e **apenas sobre o estado final**: o que ficou feito, onde e o que
eventualmente ficou pendente.

É proibido descrever o pensamento, o raciocínio ou o caminho percorrido durante
a execução, dos quais o usuário não participou.
