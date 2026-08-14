Um **projeto de testes** é o conjunto organizado de atividades, recursos, artefatos e critérios usados para verificar se um produto, sistema ou entrega atende aos requisitos esperados.

Ele não é apenas uma pasta cheia de casos de teste — o famoso cemitério de planilhas. É uma estrutura de gestão e execução que responde:

* **O que será testado?**
* **Por que será testado?**
* **Como será testado?**
* **Quem executará?**
* **Em qual ambiente?**
* **Quando termina?**
* **Como se decide se passou ou falhou?**

## Estrutura geral

```text
Projeto de Testes
├── Contexto e objetivos
├── Escopo
├── Base de teste
├── Estratégia de testes
├── Planejamento
├── Especificações de teste
├── Ambiente e dados
├── Execução
├── Gestão de defeitos
├── Evidências e rastreabilidade
├── Métricas e critérios de aceite
└── Encerramento
```

## 1. Contexto e objetivos

Explica **por que o projeto de testes existe**.

Exemplos:

* validar uma nova versão antes da publicação;
* verificar uma correção crítica;
* testar integração entre dois sistemas;
* certificar uma migração de dados;
* avaliar desempenho, segurança ou compatibilidade;
* demonstrar conformidade com requisitos contratuais.

Um objetivo precisa ser verificável:

> Confirmar que a versão 0.13 cria, registra, consulta e renderiza corretamente os datasets de cronograma em ambiente Windows.

Isso é melhor do que:

> Testar se o sistema está funcionando.

## 2. Escopo

Define as fronteiras do projeto.

### Dentro do escopo

* funcionalidades;
* componentes;
* interfaces;
* versões;
* plataformas;
* perfis de usuário;
* fluxos de negócio;
* integrações.

### Fora do escopo

Também deve ser explícito:

* desempenho não será avaliado;
* interface móvel não será testada;
* componentes de terceiros serão considerados caixas-pretas;
* migração de versões anteriores não faz parte desta rodada.

Sem isso, o teste vira a clássica missão: “já que você está olhando, testa tudo”.

## 3. Itens de teste

São os objetos concretos submetidos aos testes.

Podem ser:

* aplicação;
* API;
* comando CLI;
* biblioteca;
* arquivo;
* banco de dados;
* equipamento;
* componente construtivo;
* modelo BIM;
* documento;
* processo operacional;
* integração entre sistemas.

Exemplo:

```text
Itens de teste
├── CLI ontobdc
├── Capability storage
├── Capability view
├── Container techcenter-doc
├── Dataset cronograma
└── HTML Cronograma Geral
```

## 4. Base de teste

É o conjunto de fontes que define o comportamento esperado.

Pode incluir:

* requisitos;
* histórias de usuário;
* critérios de aceite;
* contratos;
* normas;
* especificações técnicas;
* desenhos;
* modelos;
* ontologias;
* esquemas de dados;
* documentação da API;
* registros de incidentes;
* comportamento da versão anterior.

A base de teste responde:

> De onde veio a afirmação de que o sistema deveria fazer isso?

Sem base de teste, há execução, mas não há propriamente verificação. Há apenas alguém clicando e formando opiniões.

## 5. Estratégia de testes

Define a abordagem geral.

### Níveis de teste

```text
Unitário
   ↓
Componente
   ↓
Integração
   ↓
Sistema
   ↓
Aceitação
```

### Tipos de teste

* funcional;
* regressão;
* integração;
* instalação;
* migração;
* desempenho;
* carga;
* segurança;
* usabilidade;
* compatibilidade;
* recuperação;
* confiabilidade;
* conformidade;
* teste exploratório;
* smoke test;
* sanity test.

### Técnicas

* particionamento por equivalência;
* análise de valores-limite;
* tabela de decisão;
* transição de estados;
* cenários de uso;
* teste baseado em risco;
* teste combinatório;
* análise de causa e efeito;
* teste exploratório;
* comparação com resultado de referência.

A estratégia também informa o que será:

* manual;
* automatizado;
* simulado;
* inspecionado;
* medido;
* comparado.

## 6. Condições e cenários de teste

Uma **condição de teste** é algo que precisa ser verificado.

Exemplo:

> Criação de dataset em container registrado.

Um **cenário de teste** descreve uma situação completa.

Exemplo:

> Usuário cria o dataset `cronograma` dentro do container `techcenter-doc`, gera a view e consulta o cronograma geral.

A partir dele podem surgir variações:

* container existente;
* container inexistente;
* dataset já existente;
* identificador inválido;
* storage não registrado;
* ausência de `facade.ttl`;
* falha de permissão;
* execução fora da raiz do projeto.

## 7. Casos de teste

O caso de teste especifica como verificar determinada condição.

```text
Caso de teste: CT-STORAGE-001

Objetivo:
Verificar a criação de um dataset em um container válido.

Pré-condições:
- Projeto inicializado.
- Container techcenter-doc registrado.
- Usuário com permissão de escrita.

Entrada:
ontobdc storage
  --container urn:ontobdc:storage/local/techcenter-doc
  --create cronograma

Procedimento:
1. Executar o comando.
2. Consultar o diretório criado.
3. Verificar os metadados registrados.
4. Executar a capability de view.

Resultado esperado:
- Dataset cronograma criado.
- Diretório .__ontobdc__ presente.
- facade.ttl gerado.
- Linkset criado.
- Dataset encontrado pelo mecanismo de resolução.

Critério:
Aprovado quando todas as verificações forem satisfeitas.
```

Um caso de teste normalmente contém:

* identificador;
* título;
* objetivo;
* prioridade;
* requisitos relacionados;
* pré-condições;
* dados de entrada;
* passos;
* resultado esperado;
* resultado obtido;
* estado;
* evidências;
* responsável;
* ambiente;
* versão testada.

## 8. Procedimentos ou scripts de teste

O caso diz **o que verificar**. O procedimento ou script detalha **como executar**.

Pode ser:

* instrução manual;
* script Python;
* teste Pytest;
* coleção Postman;
* pipeline CI;
* checklist de inspeção;
* sequência de comandos;
* roteiro de ensaio de campo.

Exemplo de relação:

```text
Requisito
   └── Condição de teste
       └── Caso de teste
           └── Procedimento ou script
               └── Resultado
                   └── Evidência
```

## 9. Ambiente de testes

Descreve onde os testes serão realizados.

Inclui:

* sistema operacional;
* hardware;
* versões de runtime;
* navegador;
* banco de dados;
* serviços externos;
* rede;
* permissões;
* variáveis de ambiente;
* configurações;
* ferramentas de teste;
* massa de dados;
* mocks e simuladores.

Exemplo:

```text
Sistema operacional: Windows 11
Shell: PowerShell
Python: 3.12
OntoBDC: branch techcenter-labsea
InfoBIM: versão 0.4
Navegadores: Edge e Chrome
Dados: cópia controlada de techcenter-doc
Modo de execução: local e offline
```

O ambiente deve ser reproduzível. Caso contrário, aparece a entidade mitológica conhecida como:

> “Na minha máquina funciona.”

## 10. Dados de teste

Define os dados necessários para executar os cenários.

Podem ser:

* válidos;
* inválidos;
* mínimos;
* máximos;
* incompletos;
* duplicados;
* inconsistentes;
* históricos;
* sintéticos;
* anonimizados;
* provenientes de produção.

Um conjunto de dados deve informar:

* origem;
* versão;
* formato;
* condições de uso;
* procedimento de preparação;
* procedimento de limpeza;
* resultado esperado.

## 11. Critérios de entrada e saída

### Critérios de entrada

Condições mínimas para iniciar os testes:

* build disponível;
* requisitos aprovados;
* ambiente instalado;
* dados preparados;
* funcionalidades mínimas operacionais;
* bloqueios críticos resolvidos.

### Critérios de saída

Condições para considerar a rodada concluída:

* todos os testes críticos executados;
* nenhum defeito bloqueador aberto;
* cobertura mínima atingida;
* taxa de aprovação aceitável;
* riscos residuais aceitos;
* relatório final emitido.

Exemplo:

```text
A versão pode ser publicada quando:

- 100% dos casos críticos forem executados;
- 100% dos casos críticos forem aprovados;
- não houver defeitos bloqueadores ou críticos;
- pelo menos 95% dos demais casos forem aprovados;
- todas as capabilities alteradas tiverem testes de regressão;
- as evidências estiverem associadas à versão testada.
```

## 12. Gestão de defeitos

Um defeito deve ser registrado com contexto suficiente para reprodução.

```text
Defeito
├── Identificador
├── Resumo
├── Descrição
├── Versão
├── Ambiente
├── Pré-condições
├── Passos para reprodução
├── Resultado esperado
├── Resultado observado
├── Severidade
├── Prioridade
├── Evidências
├── Componente afetado
├── Responsável
└── Estado
```

Estados comuns:

```text
Novo
→ Triado
→ Em correção
→ Corrigido
→ Em reteste
→ Encerrado
```

Ou:

```text
Novo
→ Não reproduzido
→ Rejeitado
→ Duplicado
→ Adiado
```

**Severidade** representa o impacto técnico ou operacional.

**Prioridade** representa a urgência de tratamento.

Um botão ligeiramente torto pode ter baixa severidade e alta prioridade antes de uma apresentação. A vida corporativa contém dessas elegâncias.

## 13. Rastreabilidade

A rastreabilidade conecta os elementos do projeto.

```text
Requisito
→ Risco
→ Condição de teste
→ Caso de teste
→ Execução
→ Resultado
→ Defeito
→ Correção
→ Reteste
→ Evidência
→ Decisão de aceite
```

Uma matriz simples pode ser:

| Requisito | Caso   | Resultado | Defeito | Evidência |
| --------- | ------ | --------- | ------- | --------- |
| REQ-001   | CT-001 | Aprovado  | —       | EV-001    |
| REQ-002   | CT-002 | Falhou    | BUG-014 | EV-002    |
| REQ-003   | CT-003 | Bloqueado | BUG-015 | EV-003    |

Ela permite responder:

* quais requisitos foram testados;
* quais não foram;
* quais falharam;
* quais defeitos os afetam;
* quais evidências sustentam a decisão.

## 14. Papéis e responsabilidades

Um projeto de testes pode envolver:

* gerente ou líder de testes;
* analista de testes;
* desenvolvedor;
* responsável pelo produto;
* especialista do domínio;
* usuário de aceitação;
* responsável pelo ambiente;
* responsável pela aprovação final.

Exemplo:

```text
Product Owner
└── define critérios de aceite

Analista de testes
└── deriva cenários e casos

Desenvolvedor
└── implementa testes unitários e corrige defeitos

Especialista de domínio
└── valida regras técnicas

Responsável pela release
└── toma a decisão de publicação
```

## 15. Planejamento e cronograma

Normalmente contempla:

```text
1. Análise da base de teste
2. Planejamento
3. Preparação do ambiente
4. Preparação dos dados
5. Especificação dos casos
6. Implementação dos scripts
7. Smoke test
8. Execução funcional
9. Execução de regressão
10. Correção e reteste
11. Aceitação
12. Encerramento
```

O planejamento deve considerar:

* esforço;
* dependências;
* disponibilidade das pessoas;
* ambientes;
* janelas de execução;
* tempo de correção;
* retestes;
* contingências.

## 16. Riscos

O projeto deve registrar riscos do próprio processo de teste.

Exemplos:

* requisitos incompletos;
* ambiente instável;
* massa de dados insuficiente;
* impossibilidade de reproduzir produção;
* dependência de serviços externos;
* prazo reduzido;
* ausência de automação;
* especialista indisponível;
* alterações durante a execução;
* resultados não determinísticos.

Cada risco pode ter:

```text
Risco
├── Probabilidade
├── Impacto
├── Exposição
├── Mitigação
├── Contingência
└── Responsável
```

## 17. Métricas

Métricas úteis incluem:

* casos planejados;
* casos executados;
* taxa de aprovação;
* casos bloqueados;
* defeitos por severidade;
* defeitos por componente;
* cobertura de requisitos;
* cobertura de código;
* tempo médio de correção;
* taxa de reabertura;
* falhas escapadas para produção;
* estabilidade da automação;
* riscos residuais.

A quantidade de casos executados isoladamente não diz muita coisa. É perfeitamente possível executar 800 testes irrelevantes e deixar justamente a funcionalidade crítica explodir no lançamento.

## 18. Evidências

São registros que demonstram o que aconteceu.

Podem ser:

* logs;
* capturas de tela;
* vídeos;
* arquivos de saída;
* relatórios;
* resultados de pipeline;
* hashes;
* registros de banco;
* medições;
* fotografias;
* documentos assinados;
* payloads de requisição e resposta.

A evidência deve estar vinculada a:

* caso;
* execução;
* versão;
* ambiente;
* data;
* executor;
* resultado.

## 19. Entregáveis

Um projeto de testes normalmente produz:

```text
Plano de testes
Estratégia de testes
Matriz de rastreabilidade
Especificação de cenários
Casos de teste
Scripts automatizados
Configuração de ambiente
Dados de teste
Registros de execução
Relatórios de defeitos
Evidências
Relatório de progresso
Relatório final
Termo ou decisão de aceite
```

## 20. Encerramento

No encerramento, consolida-se:

* o que foi testado;
* o que não foi testado;
* resultados;
* defeitos ainda abertos;
* desvios do planejamento;
* cobertura alcançada;
* riscos residuais;
* recomendação de publicação;
* lições aprendidas;
* artefatos que devem ser preservados.

A conclusão pode ser:

```text
Aprovado
Aprovado com ressalvas
Reprovado
Execução inconclusiva
```

## Projeto de testes versus plano de testes

A distinção é importante:

* **Projeto de testes:** todo o esforço organizado, incluindo pessoas, ambientes, atividades, casos, execuções, defeitos e evidências.
* **Plano de testes:** documento ou artefato que descreve como esse esforço será conduzido.
* **Caso de teste:** unidade específica de verificação.
* **Execução de teste:** ocorrência concreta da aplicação de um caso em determinada versão e ambiente.
* **Relatório de teste:** consolidação dos resultados obtidos.

## Modelo mínimo operacional

Para um projeto pequeno, eu usaria pelo menos:

```text
test-project/
├── README.md
├── test-plan.md
├── requirements/
├── test-cases/
├── test-data/
├── automated-tests/
├── environments/
├── executions/
├── defects/
├── evidence/
├── traceability/
└── reports/
```

E conceitualmente:

```text
TestProject
├── objective
├── scope
├── testBasis
├── testItem
├── testStrategy
├── testEnvironment
├── testDataSet
├── testScenario
├── testCase
├── testProcedure
├── testExecution
├── testResult
├── defect
├── evidence
├── risk
├── metric
└── acceptanceDecision
```

Essa última estrutura já é praticamente uma base para modelar um **container semântico de testes** no OntoBDC: requisitos, casos, execuções, defeitos e evidências como entidades relacionadas, em vez de tudo misturado numa planilha monolítica.
