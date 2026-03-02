# Estratégia de Análise de Conversas WhatsApp

Este documento discute métodos para extrair inteligência, organizar e automatizar respostas a partir de históricos de conversas do WhatsApp.

## 1. Extração de Tags e Palavras-Chave

O objetivo é identificar **sobre o que** as pessoas estão falando e quais são os **termos críticos** (projetos, pessoas, ações).

### Métodos

*   **Frequência de Termos (TF-IDF):**
    *   *Como funciona:* Calcula a relevância de palavras comparando sua frequência na conversa atual contra a frequência em todo o histórico.
    *   *Prós:* Rápido, não requer LLMs. Bom para identificar jargões técnicos únicos.
    *   *Contras:* Ignora contexto (ex: "urgente" pode ser ruído ou crítico).

*   **Reconhecimento de Entidades Nomeadas (NER):**
    *   *Ferramentas:* spaCy, NLTK.
    *   *Como funciona:* Identifica automaticamente Pessoas (PER), Organizações (ORG), Locais (LOC) e Datas.
    *   *Aplicação:* Criar tags automáticas como `envolve:João`, `empresa:Petrobras`.

*   **Extração Baseada em LLM (Recomendado para Semântica):**
    *   *Como funciona:* Enviar blocos de conversa para um modelo (ex: Gemini/GPT) com o prompt: "Resuma esta conversa em 3-5 tags técnicas e de negócio".
    *   *Prós:* Entende nuances, sarcasmo e contexto implícito.
    *   *Contras:* Custo e latência maiores que métodos estatísticos.

*   **Padrões (Regex):**
    *   *Aplicação:* Capturar códigos de projeto (ex: `PROJ-\d+`), e-mails, valores monetários.

---

## 2. Divisão em Threads / Blocos por Assunto

Conversas de chat são fluxos contínuos. Para analisar, precisamos "quebrar" em sessões lógicas.

### Estratégias de Segmentação

*   **Segmentação Temporal (Time-Gap):**
    *   *Lógica:* Se o intervalo entre duas mensagens for maior que X horas (ex: 2h), considera-se um novo tópico.
    *   *Prós:* Muito fácil de implementar (já temos `max_response_time` calculado).
    *   *Contras:* Falha se o assunto continuar no dia seguinte ("Sobre aquilo de ontem...").

*   **Segmentação Semântica (Embeddings):**
    *   *Lógica:* Converter cada mensagem (ou grupo de 3-5 mensagens) em um vetor numérico (embedding). Calcular a similaridade (cosseno) entre vetores adjacentes. Se a similaridade cair drasticamente, o assunto mudou.
    *   *Ferramentas:* `sentence-transformers`, OpenAI Embeddings.
    *   *Visualização:* Plotar a similaridade ao longo do tempo para ver os "vales" que indicam mudança de assunto.

*   **Detecção de Tópicos (Topic Modeling):**
    *   *Ferramentas:* BERTopic, LDA.
    *   *Lógica:* Agrupa mensagens não pela ordem, mas pelo conteúdo.
    *   *Exemplo:* Agrupar todas as mensagens sobre "Pagamento" independente de quando ocorreram.

*   **Abordagem Híbrida (Temporal + LLM):**
    *   1. Quebrar inicialmente por tempo (> 6h).
    *   2. Passar cada bloco para um LLM: "Este bloco contém múltiplos assuntos? Se sim, onde dividir?".

---

## 3. Sugestão de Resposta (RAG & Style Transfer)

Como sugerir respostas que pareçam com você e sejam úteis?

### Abordagens

*   **Retrieval Augmented Generation (RAG):**
    *   *O que é:* Criar um banco de dados vetorial (ChromaDB, FAISS) com todo o seu histórico.
    *   *Fluxo:*
        1. Recebe nova mensagem: "O projeto atrasou?"
        2. Busca no banco: Como você respondeu a perguntas sobre atraso no passado?
        3. LLM gera resposta baseada nesses exemplos: "Baseado no histórico, Elias costuma responder de forma direta e propor nova data. Gere uma resposta assim."

*   **Fine-Tuning (Avançado):**
    *   *O que é:* Treinar uma versão "mini" de um LLM (ex: Llama-3-8B) especificamente com seus dados de chat (`input: pergunta`, `output: sua_resposta`).
    *   *Resultado:* O modelo aprende seu vocabulário, gírias e estilo de pontuação.

*   **Few-Shot Prompting (Mais simples):**
    *   *Prompt:* "Você é Elias. Aqui estão as últimas 10 mensagens do histórico para contexto. A última mensagem recebida foi X. Sugira 3 opções de resposta (uma formal, uma curta, uma negativa)."

### Próximos Passos Sugeridos

1.  **Implementar Segmentação Temporal:** Já temos os dados de tempo. É o "low hanging fruit" para começar a ver conversas como "sessões".
2.  **Testar RAG Simples:** Indexar as mensagens extraídas e fazer perguntas ao histórico ("O que eu falei sobre o projeto X?").
