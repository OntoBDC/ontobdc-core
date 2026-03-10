# Documentação do Workbench de Análise de WhatsApp

## Resumo da Solução
Esta solução implementa um pipeline completo de ETL (Extract, Transform, Load) para dados exportados do WhatsApp. O objetivo é transformar dumps de conversas (arquivos ZIP) em pacotes de dados estruturados (Frictionless Data Packages) enriquecidos com inteligência artificial.

A solução automatiza desde a extração de mensagens até a geração de insights avançados (detecção de threads, sugestões de resposta e extração de tarefas) utilizando LLMs, organizando tudo em uma estrutura de diretórios padronizada e limpa.

## Fluxo de Trabalho (End-to-End)

### 1. Ingestão de Dados
*   **Entrada:** Arquivos `.zip` exportados diretamente do WhatsApp (função "Exportar conversa").
*   **Localização:** Os arquivos devem ser colocados no diretório:
    `projects/messages/incoming/`
*   **Padrão de Nome:** O sistema espera arquivos começando com "WhatsApp Chat with..." (padrão de exportação do app), mas processa qualquer ZIP válido nesse diretório.

### 2. Preparação (Descompactação)
*   **Script:** `ontobdc/tmp/scripts/whatsapp/whatsapp.py`
*   **Funcionamento:**
    1.  Varre a pasta de entrada em busca de arquivos `.zip`.
    2.  Utiliza a capability `ListDocumentsByNamePatternCapability` para filtrar arquivos relevantes.
    3.  Descompacta cada arquivo em uma pasta com o mesmo nome (sem a extensão `.zip`).
    4.  Se a pasta de destino já existir, ela é limpa antes da extração para garantir integridade.

### 3. Processamento e Análise
*   **Script:** `ontobdc/tmp/scripts/whatsapp/whatsapp_messages.py`
*   **Execução:** Pode ser rodado apontando para uma pasta de chat específica ou varrerá o diretório `incoming` automaticamente.
*   **Etapas:**
    1.  **Extração de Mensagens:** Lê o arquivo `_chat.txt` (ou similar) e converte o texto não estruturado em uma lista de objetos JSON estruturados (data, autor, conteúdo).
    2.  **Análise Estatística:** Calcula métricas básicas (contagem de mensagens, tempo de resposta, horários de pico).
    3.  **Gestão de Anexos:**
        *   Filtra áudios de voz (PTT) usando o padrão `PTT*.opus`.
        *   Identifica outros anexos (imagens, documentos, contatos).
        *   Gera listas JSON para `audios.json` e `attachments.json`.
    4.  **Organização de Recursos:** Cria (ou atualiza) a pasta oculta `.__ontobdc__` dentro do diretório do chat para armazenar todos os metadados gerados.

### 4. Inteligência (Integração com LLM)
A solução prepara o terreno para análise semântica avançada.
*   **Geração de Prompt:** O script gera automaticamente o arquivo `.__ontobdc__/llm_prompt.md`.
    *   Este arquivo combina um template padronizado (`ontobdc/prompt/whatsapp/analyze_chat.md`) com as mensagens extraídas do chat.
*   **Análise Externa:** O usuário envia o conteúdo deste prompt para uma LLM (como Gemini, GPT-4, etc.).
*   **Retorno:** A resposta da LLM (um JSON contendo threads, sugestões e tarefas) deve ser salva como `.__ontobdc__/insights.json`.
*   **Processamento Automático:** Ao re-executar o script `whatsapp_messages.py`, ele detecta a presença do `insights.json` e automaticamente o divide em:
    *   `threads.json`
    *   `suggestions.json`
    *   `tasks.json`

### 5. Consolidação (Data Package)
*   **Padronização:** Gera um arquivo `datapackage.json` na raiz da pasta do chat, seguindo a especificação Frictionless Data.
*   **Conteúdo:** O pacote descreve e inclui todos os recursos gerados:
    *   `messages.json`
    *   `statistics.json`
    *   `audios.json`
    *   `attachments.json`
    *   `threads.json`, `suggestions.json`, `tasks.json` (se disponíveis)
*   **Benefício:** Isso torna o dataset portável, auto-descritivo e pronto para consumo por outras ferramentas ou scripts de análise.

## Padrões Adotados

### Estrutura de Diretórios
```
projects/messages/incoming/
└── WhatsApp Chat with Nome do Contato/
    ├── datapackage.json          # Descritor do pacote (Frictionless)
    ├── _chat.txt                 # Log original (raw data)
    ├── IMG-2023...jpg            # Mídia original
    └── .__ontobdc__/             # Pasta de recursos gerados (Metadados)
        ├── messages.json         # Mensagens estruturadas
        ├── statistics.json       # Métricas básicas
        ├── audios.json           # Lista de áudios PTT
        ├── attachments.json      # Lista de outros anexos
        ├── llm_prompt.md         # Prompt pronto para LLM
        ├── insights.json         # (Input Manual) Resposta bruta da LLM
        ├── threads.json          # (Gerado) Conversas agrupadas
        ├── suggestions.json      # (Gerado) Sugestões de resposta
        └── tasks.json            # (Gerado) Tarefas extraídas
```

### Convenções
*   **Resource Folder:** `.__ontobdc__` (com ponto inicial) para manter a raiz do chat limpa, contendo apenas os arquivos originais e o descritor do pacote.
*   **Nomenclatura:**
    *   `statistics.json` em vez de `analysis.json` para evitar ambiguidade com análises mais profundas.
    *   Pacotes Frictionless nomeados de forma sanitizada (ex: `whatsapp-chat-nome-do-contato`).
*   **Automação:** Scripts idempotentes. Podem ser rodados múltiplas vezes sem duplicar dados ou corromper o estado; eles atualizam o que for necessário.

## Resultados Obtidos
*   **Redução de Carga Cognitiva:** Eliminação da necessidade de reler históricos inteiros. O sistema entrega resumos, tarefas e rascunhos de resposta.
*   **Organização:** Transformação de pastas caóticas de exportação em datasets organizados e consultáveis.
*   **Portabilidade:** O uso de Frictionless Data Packages garante que os metadados viajem junto com os dados brutos de forma padronizada.
*   **Flexibilidade:** A arquitetura desacoplada permite trocar o modelo de LLM ou ajustar os prompts sem alterar o código de processamento core.
