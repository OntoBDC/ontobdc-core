# Relatório: Modelo de Interface do OntoBDC nas Conversas de Domínio (docs 02/08, 07/08, 08/08)

**Data de geração:** 8 de agosto de 2026
**Fontes analisadas:**
- `presentation/` (pacote `ontobdc-view`, componentes Web Components)
- `ontobdc/lab/presentation-tile/index.html` (protótipo `onto-tile` / `presentation-surface`)
- `docs/notes/domain-conversations/2026-08-01-briefcase-perspectives-checkpoint-2231.md`
- `docs/notes/domain-conversations/2026-08-01-briefcase-perspectives-summary.md`
- `docs/notes/domain-conversations/2026-08-01-briefcase-perspectives-transcript.md`
- `docs/notes/domain-conversations/2026-08-02-briefcase-perspectives-transcript-continuation-01.md`
- `docs/notes/domain-conversations/2026-08-03-offline-money-and-44-legacy.md`
- `docs/notes/domain-conversations/2026-08-07-presentation-interoperability-events-ble-dock-transcript.md`
- `docs/notes/domain-conversations/2026-08-08-ddock-presentation-layer-event-model.md`

Nota metodológica: o documento de 02/08 (`briefcase-perspectives-transcript-continuation-01.md`) é majoritariamente sobre a camada econômica/dBriefcase (doações, propaganda consentida, listas de presentes, compra coletiva etc.) e é tratado aqui apenas na parte final, onde nasce o conceito de **Dock**, servindo de baseline histórico para os outros dois documentos, que são o núcleo do modelo de interface.

---

## 1. Linha do tempo / evolução conceitual do modelo de apresentação

### Doc 1 — 2026-08-02 (briefcase-perspectives-continuation-01)
Não existe ainda "Presentation Surface" nem "Tile". O que existe é a **primeira concepção da Dock**, motivada por um desejo pessoal do Elias ("a dock... imagina... só bota o celular ali na paradinha"). Nessa versão:
- a Dock é vista como **corpo físico ativo** que troca dados com o celular (herdada de uma "ideia antiga da Dockstation");
- ela **não carrega identidade do usuário** — oferece energia, microfone, alto-falante, eventualmente tela, conexão com TV/luz/carro/ambiente;
- o celular leva "a mente"; a Briefcase leva "memória e contexto";
- princípio central, citado literalmente: **"quando tira o telefone, você vai embora dali inteiro"**;
- casos de uso detalhados: sala, cozinha, carro (pedir para ir a um compromisso e achar combustível no caminho), mesa de reunião, **hotel** (identificado como o melhor piloto comercial: "O hotel fornece o corpo e os serviços. O celular fornece identidade, idioma, preferências, pagamento e inteligência");
- plano de execução em 3 degraus: (1) dock lógica/protocolo, (2) protótipo feio com hardware de prateleira (carregador Qi, caixa de som BT, microfone, NFC), (3) hardware próprio só depois de validado;
- surge um parceiro real de hardware (dono de provedor de internet + fábrica de cachaça) interessado em "hardware barato com valor percebido alto" — o que empurra a Dock de "desejo pessoal" para "hipótese de produto".

Neste documento a Dock ainda é conceitualmente **"inteligente do domínio"** (ela "entende" o carro, o hotel) — isso será revisto no doc seguinte.

### Doc 2 — 2026-08-07 (presentation-interoperability-events-ble-dock-transcript)
Este é o documento onde a arquitetura de interface realmente nasce, em duas grandes fases:

**Fase A (seções 1–12, reconstrução/contexto):** ponto de partida é a nostalgia de RAD (Delphi/VCL data-aware, VB6/ActiveX) e o incômodo de reimplementar HTML/CSS/JS "do zero" a cada tela. Daí nasce a separação `Command → Response semântico → Renderer` ("`ListResponse` deve dizer 'isto é uma lista', e não 'isto é uma tabela'"), a ideia de **componentes semânticos** reutilizáveis (Observer-like, comunicando-se por eventos sem se conhecerem), o exemplo do Gantt (`Schedule/TaskTimeline` é o conceito, `Gantt` é só uma representação), tokens semânticos de tema (light/dark/high contrast/system/density/emphasis/variant/brand), e o exemplo do Button levando à decisão técnica **Custom Elements + Shadow DOM** com a exigência de longevidade de 50 anos.

**Fase B (seção 13 em diante, "trecho integral"):** aqui entram Event Bus, Event Bridge, BLE e a **redefinição da Dock**:
1. §13.1–13.4: formalização de Bus (`EventTarget`+`CustomEvent`, papel "aconteceu algo no sistema") vs Bridge (adapter para transporte externo: WebSocket, SSE, WebRTC, BLE, Serial, USB, mesh); analogia "Bus = barramento CAN do carro; Bridge = gateway que leva mensagens do barramento para outra rede".
2. §13.5: **BLE Advertising como transporte de eventos** — pacotes compactos (31 bytes legado preferido sobre Extended Advertising) carregando um "wire protocol" mínimo OntoBDC que o app expande em evento semântico completo. Regra: mandar fatos/intenções semânticas (`EmergencyActivated`, `PersonDetected`), nunca comandos crus ("mostre vermelho").
3. §13.7: retomada da Dock antiga do doc 1 (via busca no repo errado, corrigida).
4. §13.8: **a virada conceitual decisiva** — Elias propõe explicitamente separar Dock de inteligência de domínio: *"a dock ser um conceito, físico ou digital, para armazenamento e despacho de eventos (ainda com zero inteligência). O emissor, no caso do carro, ser um Agent que troca dados com a dock."* A partir daqui: **Agent = domínio; Dock = store-and-forward de eventos; Bridge = transporte; Bus = distribuição local.**
5. §14 (resumo): Dock passa a ser definida funcionalmente: *"um ponto de encontro persistente entre Agents, onde eventos podem ser depositados e posteriormente consumidos, independentemente de os participantes estarem simultaneamente presentes"* — termo cunhado: **store-and-forward semântico**.
6. §18: **"a grande revelação": o navegador pode assumir o papel de Dock digital → nasce o termo `dDock`** (papel/runtime, distinto do host que o executa — o browser é só um host capaz de hospedar dDock, Agents, Renderer, Components e Bridges simultaneamente).
7. §19: inversão do modelo de UI — a tela deixa de ser construída antecipadamente e passa a ser uma **superfície vazia montada em runtime por eventos** ("scene/scene graph", **Presentation Surface**), analogia explícita com jogos.
8. §20–23: pesquisa e descarte parcial de A2UI/AG-UI como fundação (útil só como referência de catálogo/protocolo, não resolve encapsulamento visual determinístico); prova prática de um botão 100% autocontido (Custom Element + Shadow DOM fechado) sem framework algum — commit registrado em `EliasMPJunior/my-desktop`.
9. §24–26: ressurreição do conceito de **Live Tiles** (Windows 8/Windows Phone) como referência histórica; nasce a distinção **Tile (unidade espacial) vs Component (unidade interna de UI encapsulada)**.
10. §27–30: a Surface **começa vazia e é construída pelo uso** — Tiles novos sobem para a região prioritária, antigos descem; Tiles podem ser disparados por clique, voz, LLM, tempo, localização e **Dock** (todos tratados como fontes equivalentes de intenção/evento).
11. §34–37: refinamento — recência não é só ordenação, é a **própria navegação** ("topo = agora; abaixo = recentemente; mais abaixo = passado ainda acessível"); pinning como exceção controlada com densidade adaptativa; benchmarking extenso (Windows Phone Live Tiles, Android Widgets, Apple Smart Stack, Lifestreams/Yale anos 90, Windows Timeline, activity-based computing) — conclusão: nenhum paradigma existente combina todos os elementos simultaneamente.
12. §38–43: cálculo de grid não é fixo por dispositivo ("celular = 8×16" é descartado) — passa a ser **calculado** a partir de largura útil, tamanho lógico de slot e gutter (`C = floor((W+G)/(S+G))`); nasce o conceito de **Presentation Profile** (distância de visualização, modalidade de entrada, densidade, contraste, restrições de acessibilidade/segurança) que parametriza o cálculo; Tile é proposto como candidata a **unidade universal de apresentação espacial** — mesma informação (ex. temperatura) materializando-se de `23°` (display mínimo) até gráfico rico (Tile grande) ou visualização de videowall.
13. §44: dockstation física com display monocromático barato reaparece como exemplo concreto de Presentation Surface mínima, sem inteligência de domínio.
14. §47: estado conceitual final do doc — cadeia completa Response → Agent → Bus → Bridge → Dock/dDock → Presentation Agent/Renderer → Presentation Surface → Grid/Slot Engine → Tile → Component → Context.

### Doc 3 — 2026-08-08 (ddock-presentation-layer-event-model)
É o documento de **consolidação formal**, escrito como "manual de implementação arquitetural em evolução". Ele:
- fixa a invariante **"Toda dDock possui uma PresentationLayer"**;
- formaliza os **três escopos de evento** (Component Event / Presentation Global Event / External Event) com regras precisas de promoção/redução de escopo;
- introduz o **Talking Dinosaur Test** como heurística de revisão para não vazar decisões de implementação Browser para o contrato universal;
- define o **contrato de negociação `TilePresentationRequest`** com blocos `required` / `optional` / `extra`, capacidades espaciais do Tile (`minColumns/minRows/maxColumns/maxRows/preferredColumns/preferredRows`) e o fluxo de aceite/rejeição;
- introduz `PresentationCapacity` como abstração acima de `columns × rows` (browser-specific);
- introduz o **Presentation System Log** (barra de depuração que evolui para conceito arquitetural de observabilidade da PresentationLayer);
- fecha com uma lista de decisões assumidas e questões ainda abertas.

Ou seja: doc1 → gera a ideia física da Dock; doc2 → desconstrói a Dock em Agent+Dock+Bridge+Bus, inventa dDock, Presentation Surface e Tile; doc3 → formaliza tudo isso em um modelo de escopo de eventos e um protocolo concreto de negociação Surface↔Tile.

---

## 2. O modelo de Dock

### 2.1 Definição evolutiva
- **Doc 1 (versão inicial, "produto"):** Dock = corpo físico do ambiente (energia, mic, alto-falante, tela, conexão com TV/luz/carro), sem identidade do usuário. Ela "entende" implicitamente o ambiente (ex.: sabe falar com o carro).
- **Doc 2 §13.8 (correção decisiva):** Dock passa a ter **zero inteligência de domínio**. Quem entende o carro é um `Car Agent`; a Dock só recebe, guarda e despacha eventos. Citação: *"O Agent entende o domínio. O Bridge entende o transporte... A Dock entende somente eventos."*
- **Doc 2 §14.13:** definição funcional final: *"Dock é um ponto de encontro persistente entre Agents, onde eventos podem ser depositados e posteriormente consumidos, independentemente de os participantes estarem simultaneamente presentes."* Pode ser física (caixinha no carro) ou digital (processo, serviço local, endpoint/"caixa postal de eventos").
- **Doc 2 §18:** generalização máxima — **o navegador é um host que pode executar o papel de dDock**, junto com Agents, Renderer, Components e Bridges, sem que os papéis se confundam.
- **Doc 3 §1:** definição final e citável: *"A `dDock` é a infraestrutura responsável por receber, armazenar e entregar eventos. Ela não interpreta o domínio dos eventos."* E a invariante: **"Toda dDock possui uma PresentationLayer."**

### 2.2 Capacidades expostas pela Dock
- receber, armazenar (store-and-forward), entregar/despachar eventos;
- replay quando aplicável;
- retenção/TTL;
- identidade técnica de origem/destino;
- permitir assinatura/consulta;
- eventualmente confirmar recebimento;
- **nunca** interpretação semântica de domínio.

### 2.3 Relação com Presentation Surface / Tiles
A Dock é a infraestrutura de eventos; a `PresentationLayer` é uma camada que toda dDock possui e é responsável por "materializar, manifestar ou tornar perceptível" informação (doc3 §1). A `Presentation Surface` e os `Tiles` são explicitamente **"uma forma possível de implementação da PresentationLayer, não a definição da PresentationLayer inteira"** (doc3 §10, decisão nº11 da lista de §16). Uma dDock pode ter PresentationLayer materializada como: LED único, log textual, display monocromático 128×64, ou uma Presentation Surface rica com múltiplos Tiles.

### 2.4 Casos de uso concretos discutidos
- **Carro:** Car Agent observa CAN bus/OBD (velocidade, combustível, ignição, portas), publica eventos na Dock; celular sincroniza ao entrar no veículo, mesmo que os eventos tenham nascido horas antes ("Car Agent pode ter colocado eventos na Dock durante horas. Quando o telefone entra no carro, sincroniza o que interessa.").
- **Hotel** (doc1): identificado como "melhor piloto comercial" — dock no quarto expõe luzes/cortina/ar-condicionado/TV/room service/recepção/checkout; personalização entra e sai com o hóspede. Citação: *"O quarto ganha uma interface pessoal durante a hospedagem, mas não retém as contas e os dados do hóspede."*
- **Dockstation com display monocromático barato** (doc3 §11 e §44): a Dock/PresentationLayer decide materializar `FuelLevelChanged: 18%` como texto simples "COMBUSTIVEL 18%" num display 128×64, sem que a Dock saiba o que é combustível.
- **Mesa de reunião, casa, carro, hotel** (recorrente): "cada lugar tem uma Dock" e Agents locais.
- Gatilho de apresentação: colocar o celular numa Dock específica pode disparar reorganização da Presentation Surface (doc2 §30: "Dock: ao colocar o celular em determinada Dock/dDock, mudar a composição da superfície").

---

## 3. O modelo de eventos

### 3.1 Doc 2 — vocabulário original (Bus/Bridge/DOM Event)
- **DOM Event**: evento físico local ("aconteceu algo comigo") — click, pointerdown, focus etc. Pode atravessar Shadow DOM com `bubbles`+`composed`.
- **Event Bus**: implementado sobre `EventTarget`+`CustomEvent`+`addEventListener`+`dispatchEvent`; distribui eventos semânticos ("aconteceu algo no sistema") independente da árvore DOM. Pode ser um `EventTarget` isolado, não necessariamente o `document`.
- **Event Bridge**: adapter que liga o Bus a um transporte externo (WebSocket, SSE/`EventSource`, HTTP/`fetch`, WebRTC DataChannel, BLE/Web Bluetooth, Web Serial, WebUSB, `BroadcastChannel`/`postMessage`/`MessageChannel` para contextos locais do browser). Regra de ouro: **"o componente jamais deveria saber qual transporte está sendo usado."**
- **Envelope de evento** (proposto desde cedo): id único, tipo, origem, timestamp, payload, versão do contrato, `correlationId`, `causationId` — para permitir reconstrução de cadeias causais ("por que essa tela mudou? recebeu PersonSelected. quem gerou? o componente X. por quê? recebeu SearchResultActivated.").
- **Estado ≠ evento**: `ButtonDisabled` é evento (fato ocorrido); "o botão está disabled" é estado. Um componente que nasce depois do evento não pode depender de tê-lo ouvido — precisa de state store/event store/replay.
- Nomenclatura semântica exigida (nunca `onclick`): `ActionInvoked`, `NavigationRequested`, `SelectionChanged`, `PersonSelected`, `PersonDetected`, `EmergencyActivated`, `MeasurementReceived`, `TaskApproved`, `ShowSchedule`.

### 3.2 Doc 3 — formalização em três escopos (o modelo "oficial" atual)

```
Component Event          "aconteceu comigo"
Presentation Global Event "aconteceu nesta PresentationLayer"
External Event            "isso importa além desta PresentationLayer"
```

1. **Component Event**: origem e significado imediato pertencem à implementação concreta (ex.: `click`, `pointerdown`, `focus`, `blur`, `input`, `change`, `mouseenter`, fim de animação/resize; ou fora do HTML: botão físico pressionado, LED terminou ciclo, encoder girado, síntese de voz terminou frase, controle remoto recebeu tecla). **Regra**: "Evento físico/local não é automaticamente evento semântico." Pode morrer nesse nível (ex.: `pointermove`).

2. **Presentation Global Event**: escopo de toda aquela instância da PresentationLayer (não da dDock, não da rede, não do sistema inteiro). Distribuído por um `Presentation Event Bus` (no browser: `EventTarget`+`CustomEvent`). Exemplos: `ActionInvoked`, `TileSelected`, `TileActivated`, `EntitySelected`, `ContextActivated`, `PresentationRequested`, `PresentationChanged`, `TilePinned`, `TileResized`, `SurfaceChanged`, `NavigationIntent`, `ShowDetailsRequested`. **Regra**: "Componentes não precisam conhecer outros componentes. Eles conhecem o contrato de eventos globais da PresentationLayer."

3. **External Event**: cruza a fronteira PresentationLayer ↔ dDock, em qualquer direção. Exemplos de entrada: `TaskAssigned`, `EmergencyActivated`, `PersonDetected`, `MeasurementChanged`, `MeetingStarting`, `ContextRequested`, `ShowSchedule`, evento vindo de BLE, de outro Agent, de replay, de outra dDock. Exemplos de saída: `TaskApproved`, `EntitySelected` (quando tem significado além da UI), `ContextChanged`, `CommandRequested`, `AcknowledgementRequested`. **Regra**: "Só deve virar External Event aquilo que possui significado fora da PresentationLayer." (evita "transformar a dDock em um esgoto de eventos de UI")

**Promoção/redução de escopo** — não é uma fila obrigatória; cada evento pode morrer onde nasceu. Exemplo de saída completo:
```
click → ActionInvoked(action="approve-task") → TaskApprovalRequested(task=123) → dDock
```
Exemplo de entrada:
```
EmergencyActivated → dDock entrega → PresentationAlertRequested → LED pisca / Tile aparece / voz fala / log registra
```

**Regra de ouro** (doc3 §14): *"O evento sobe de escopo somente quando seu significado sobe de escopo."*

### 3.3 Fluxos (sequência)
- **Saída** (doc3 §8): Usuário → Componente (Component Event) → Bus (Presentation Global Event) → PresentationLayer → dDock (External Event) → armazenar/despachar → Agent externo.
- **Entrada** (doc3 §9): Agent externo → dDock (External Event) → PresentationLayer → Bus (traduz/publica) → Componente interessado → manifestação para o usuário.

### 3.4 BLE como caso especial de External Event
BLE Advertising é tratado explicitamente como **transporte**, não feature de domínio — os eventos que chegam por BLE entram no fluxo de "entrada" como qualquer outro External Event (ver seção 5 abaixo).

### 3.5 Responsabilidades por peça (consolidado doc3 §13 / doc2 §14.14 e §31)
- **dDock**: receber, armazenar, entregar, replay, retenção/TTL, despacho, identidade técnica de origem/destino. Sem inteligência de domínio.
- **PresentationLayer**: receber eventos externos destinados à apresentação; converter em eventos globais quando necessário; distribuir; materializar via renderers/componentes; converter interações locais em eventos de apresentação; externalizar só o que tem significado fora da camada.
- **Component/Renderer**: interação concreta, manifestação concreta, eventos locais, tradução entre primitiva física/tecnológica e contrato de apresentação.
- **Agent**: entende o domínio, produz fatos/intenções semanticamente significativos, consome eventos de domínio, age quando autorizado.
- **Response** (do doc2, fase A): objeto semântico devolvido por um Command — não descreve a tela, descreve o significado (lista, detalhe, ajuda, entidade).

---

## 4. Protocolo de negociação de capacidades Tile ↔ Surface

Este é o núcleo formal do doc3 (§20–31), ponto mais avançado e mais "pronto para implementação" do material.

### 4.1 Estrutura do pedido
```
TilePresentationRequest
├── required
├── optional
└── extra
```
Regra fundamental: a classificação **não é propriedade fixa** de um atributo — é decidida pela Surface a cada solicitação. Citação: *"`transparentBackground` não é, por natureza, obrigatório nem opcional. É a Surface que determina a força daquela exigência."*

### 4.2 `required`
Requisitos que **devem** ser atendidos. Se o Tile não suporta algum, deve **rejeitar explicitamente** a negociação:
```yaml
status: rejected
reason: unsupported_requirement
requirement: transparentBackground
requestedValue: true
```
A Surface então decide o fallback: oferecer outra área, outra representação, outro Tile, relaxar exigência (se a regra permitir), não materializar, ou apresentar erro/estado alternativo. Nota: implementação JS pode usar exception internamente, mas o conceito arquitetural é "um requisito obrigatório não atendido produz uma falha explícita de negociação de apresentação" (não deve depender de exceptions no contrato semântico).

### 4.3 `optional`
Preferências tratadas em regime **best effort**: atender completamente, parcialmente, ignorar, ou mapear para equivalente. Falha em item optional **não invalida** a apresentação; propriedade desconhecida deve poder ser ignorada.

### 4.4 `extra`
Contexto adicional (timezone, geolocation, localeContext.measurementSystem, ambientLight, deviceOrientation etc.), sem exigência de conformidade. **Regra**: "Uma chave desconhecida em `extra` nunca deve invalidar a apresentação" — permite evolução do protocolo sem quebrar Tiles antigos.

Semântica resumida dos três blocos:
```
required   "isto precisa ser atendido"
optional   "eu prefiro isto, se você conseguir"
extra      "estou te contando isto; use se for útil"
```

### 4.5 Capacidades espaciais do Tile (Browser)
```yaml
spatialCapabilities:
  minColumns / minRows / maxColumns / maxRows
  preferredColumns / preferredRows   # opcional
```
Regra: `2×4` e `4×2` **não são equivalentes** para o Tile, mesmo tendo a mesma área — daí a necessidade de dimensões independentes por eixo, não área escalar. A Surface informa `availableArea: {columns, rows}` na materialização, e "O contrato espacial Browser deve trabalhar primeiro com unidades lógicas de grid, não com pixels físicos como identidade universal do Tile."

### 4.6 Exemplo completo de negociação (doc3 §30)
Pedido com `required: {language, availableArea, transparentBackground}`, `optional: {theme, font, colors}`, `extra: {timezone, geolocation}`; capability do Tile declarando `spatialCapabilities` + `presentationCapabilities: {transparentBackground: true, themes: [light, dark], fontOverride: false, colorOverride: true}`; resultado `status: accepted` com `allocation`, `applied`, `ignoredOptional: [font]`, `usedExtra: [timezone]`. Se o Tile não suportasse `transparentBackground`, o mesmo pedido geraria `status: rejected`.

### 4.7 `PresentationCapacity` — abstração acima da geometria Browser
Para não fixar `columns×rows` como universal, doc3 §28 propõe `PresentationCapacity` como conceito geral, do qual `Browser Capacity (columns/rows)` é um caso, e `Talking Dinosaur Capacity (tempo disponível, quantidade de fala, formalidade/estilo)` é outro caso hipotético — reforçando que o objetivo não é implementar um renderer de dinossauro, mas impedir que `columns`/`rows` virem propriedades universais indevidas.

### 4.8 Talking Dinosaur Test
Heurística de revisão arquitetural (doc3 §19), citação literal:

> **"O dinossauro falante consegue interpretar isso de alguma forma coerente?"**

Se uma propriedade só faz sentido por causa de DOM/CSS/mouse/viewport/pixels, é Browser-specific (ex.: `grid-column: span 4`, `pointerenter`). Se expressa intenção/capacidade reinterpretável por outro meio, pode pertencer à abstração geral (ex.: `EmergencyActivated`, `language=pt-BR`, `importance=critical` — que pode virar cor, som, volume, animação, prioridade; `availableArea` — espaço 2D no browser, "quanto pode falar" no dinossauro; `theme=dark` — fundo escuro no browser, tom mais baixo/sussurro numa voz).

### 4.9 Regras consolidadas do contrato (doc3 §31, lista de 16 regras)
Principais: pedido dividido em três blocos; mesma propriedade pode mudar de bloco entre pedidos; todo `required` precisa ser atendido; item obrigatório não suportado gera rejeição explícita; falha em `optional` não invalida; `optional` desconhecido pode ser ignorado; `extra` é contexto, nunca requisito, chave desconhecida nunca invalida; Surface decide o fallback pós-rejeição; Tile declara limites espaciais min/max e preferências separadamente; área preserva dimensões independentes (`columns×rows`); pixels concretos pertencem ao renderer, não ao contrato universal; Browser é primeira implementação, não definição ontológica da PresentationLayer; toda adição ao contrato passa pelo Talking Dinosaur Test antes de virar conceito universal.

### 4.10 Questões explicitamente em aberto (doc3 §17 e §33)
Schema formal definitivo do `TilePresentationRequest`; nome definitivo de `PresentationCapacity`; **protocolo de descoberta de capabilities do Tile ainda não definido** (síncrono, declarativo ou orientado a eventos?); forma de resposta da negociação; taxonomia de themes; representação de cores/fontes; relação locale↔language; contrato de identidade/permissões; tratamento de geolocalização sensível; persistência de pedidos/resultados; lifecycle do Tile; política de fallback da Surface; relação entre negociação espacial e recência/prioridade dos Tiles; se `preferredColumns/Rows` bastam ou Tiles precisarão de múltiplos perfis espaciais discretos.

---

## 5. BLE e proximidade/pareamento

Tratado exclusivamente no doc 2 (doc 3 só cita BLE en passant como fonte de External Event de entrada, doc3 §6).

### 5.1 Gatilho da discussão
Elias pergunta se dá para colocar um "evento padrão OntoBDC" numa "mensagenzinha" BLE que o app escuta e aplica, assumindo permissões concedidas (background, scan, etc.).

### 5.2 Distinções técnicas estabelecidas
- **BLE Advertising** é o mecanismo relevante (não conexão GATT tradicional): dispositivo transmite pacotes periódicos que um celular em scan recebe sem parear.
- Advertising legado: **31 bytes** por pacote. BLE LE Extended Advertising: até ~1.650 bytes (variável por hardware/SO). **Decisão explícita: preferir os 31 bytes como contrato mínimo**, por compatibilidade com o maior universo de dispositivos possível.
- Codificação proposta: binária compacta (não JSON-LD, seria desperdício de bytes) — algo como "protocolo OntoBDC versão 1; evento 37; dispositivo 142; valor 3", que o app expande semanticamente ao receber (ex.: evento 37 = `ToolEnteredArea`).
- Permissões Android citadas: `BLUETOOTH_SCAN`, `BLUETOOTH_ADVERTISE`, `BLUETOOTH_CONNECT`. iOS: Core Bluetooth, com restrições próprias da Apple em background.
- **Regra de design**: mandar eventos/fatos semânticos, nunca comandos crus. Citação: *"não mandar 'comandos' crus tipo 'abra a tela 4'. Mandaria eventos/fatos semânticos... 'EmergencyActivated'... 'PersonDetected, João'."* Justificativa: o mesmo pacote pode disparar comportamentos diferentes em quem estiver ouvindo (tablet mostra tela, outro dispositivo toca alerta, logger registra, gateway sincroniza depois).
- Conclusão arquitetural: **"BLE não seria uma funcionalidade especial da aplicação. Seria só mais um transporte do protocolo de eventos."** — mesmo status de WebSocket, SSE, WebRTC, Serial, USB.

### 5.3 Casos de uso citados
Crachá que entra numa região, ferramenta que aparece perto de um receptor, equipamento que muda de estado, botão físico pressionado, sensor acusando algo, beacons, tudo funcionando "sem internet". Também citada a integração dock↔hardware barato (Qi charging, caixa de som BT, NFC, Matter para luz/cortina/ar-condicionado no cenário do hotel — doc1).

### 5.4 Proximidade como gatilho de apresentação
No doc2 §30, "proximidade"/"BLE"/"Dock" são listados junto com tempo e localização como **gatilhos equivalentes de materialização/reorganização de Tiles na Presentation Surface** — nenhum deles é tratado como caso especial; todos produzem eventos/intenção que alimentam o mesmo mecanismo.

Não há, nestes documentos, um modelo formal de **pareamento** (handshake completo, autenticação de dispositivo, etc.) — apenas o mecanismo unidirecional de advertising/scan e a assunção de que permissões de SO já foram concedidas. É uma lacuna explícita a preencher depois.

---

## 6. Interoperabilidade entre produtos/gateways/apresentações

### 6.1 Interoperabilidade de apresentação (doc2, seções 3–4)
O termo evoluiu de "interoperabilidade visual" para **"interoperabilidade de apresentação"**, porque a saída pode não ser visual (HTML, Flutter, PDF, terminal, widget, totem, voz/Alexa). O mecanismo central é:
```
Command → Response semântico (não sabe como desenhar) → Renderer específico do target → materialização concreta
```
Um `ListResponse` pode virar data grid HTML, cards mobile, lista Flutter, tabela paginada em PDF, lista textual em terminal, enumeração falada em Alexa — **sem que o Command/Response conheça a existência de bibliotecas concretas** (ex.: Tabulator escondido atrás do renderer HTML).

### 6.2 Capability discovery e fallback
Um renderer declara o que suporta; quando não há equivalente, deve haver "fallback semântico previsível" (voz não tem Gantt visual → vira descrição/lista falada; mapa degrada para texto; PDF não tem o mesmo modelo de interação de HTML). Isso é chamado de propriedade essencial da "máxima interoperabilidade".

### 6.3 Interoperabilidade entre superfícies físicas radicalmente diferentes (doc2 §41–43)
A tese central que fecha o doc2: o mesmo Tile (mesma unidade semântica de informação) pode se materializar de forma mínima (relógio, display monocromático de dockstation) até rica (desktop, TV, videowall), **sem obrigar aplicações/páginas diferentes por dispositivo**. Citação final do doc2, que resume toda a tese:

> "**Tile aparece como a unidade espacial que faltava para transformar interoperabilidade de apresentação em algo concreto: a mesma informação pode se materializar de forma mínima ou rica conforme a Surface, de um display monocromático barato a um videowall, sem obrigar a existência de páginas ou aplicações visuais diferentes para cada dispositivo.**"

### 6.4 Interoperabilidade entre "gateways"/ambientes via Dock/dDock
No doc1/doc2, a Dock funciona como ponto de troca entre ambientes fisicamente diferentes (carro, hotel, casa) mantendo a mesma identidade/Briefcase do usuário — "qualquer lugar pode virar o seu computador pessoal por alguns minutos" (doc1). No doc2 §14.14, isso é generalizado: qualquer Dock física pode ser reimplementada como dDock digital hospedada em qualquer runtime (o browser sendo o primeiro caso).

### 6.5 Regras que preservam a interoperabilidade (doc2 §16 e §32, "princípios que atravessaram toda a conversa")
Lista consolidada e citável:
1. Não amarrar semântica à apresentação concreta (`List`≠`table`, `Schedule`≠`Gantt`).
2. Não amarrar evento semântico a evento físico de UI (`ActionInvoked`≠`click`).
3. Não amarrar protocolo a transporte (mesmo evento cruza WebSocket, SSE, BLE, USB, WebRTC, mesh).
4. Não amarrar componente ao CSS da página hospedeira (Web Component/Shadow DOM).
5. Não amarrar identidade ao ambiente (ambiente oferece capacidades; identidade fica com usuário/Briefcase).
6. Não colocar inteligência de domínio na Dock.
7. Não exigir simultaneidade entre produtor e consumidor de eventos.
8. Offline como propriedade fundamental, não exceção.
9. Preferir primitivas/standards duráveis (visando longevidade).
10. Projetar para degradação/fallback entre superfícies diferentes.
11. Separar estado de evento.
12. Separar estado semântico de estado efêmero de interação (hover só existe em superfícies com ponteiro).
13. Bibliotecas de terceiros só como detalhes substituíveis de renderer/adapter.
14. Contrato pequeno, explícito e versionável.
15. Meta declarada de longevidade extrema — reabrir décadas depois preservando significado e identidade visual.

### 6.6 Reflexo direto no modelo econômico (doc1)
Embora fora do escopo estrito de interface, vale registrar a conexão: a interoperabilidade de apresentação é o que permite, por exemplo, que a mesma Briefcase de um teatro seja aberta em qualquer dispositivo via QR code sem "conta" — reforçando a tese de viralização de baixo atrito descrita no doc1 ("QR Code → baixa .obdc → abre no OntoBDC → navega").

---

## 7. Citações literais adicionais relevantes (com atribuição)

**Sobre a Dock (doc1, ChatGPT):**
> "A dock não precisa 'te conhecer'. Ela só oferece corpo: energia; microfone; alto-falante; talvez tela; conexão com TV, luz, carro ou ambiente. O celular leva a mente. A Briefcase leva memória e contexto."

**Sobre a separação Dock/Agent (doc2, Elias, §13.8 — a virada conceitual):**
> "a dock ser um conceito, físico ou digital, para armazenamento e despacho de eventos (ainda com zero inteligência). O emissor, no caso do carro, ser um Agent que troca dados com a dock"

**Resposta do ChatGPT à virada:**
> "A Dock deixa de ser 'o negócio que sabe falar com o carro'. Ela vira uma infraestrutura burra de entrada, armazenamento temporário e despacho de eventos... Eu chamaria isso de store-and-forward semântico."
> "o ambiente deixa de precisar entender o usuário e o usuário deixa de precisar entender o ambiente. Os dois lados só precisam concordar sobre eventos e capabilities."

**Sobre Bus vs Bridge (doc2, ChatGPT, explicação "sem código"):**
> "O evento do DOM diz mais ou menos 'aconteceu alguma coisa aqui'. O Event Bus diz 'aconteceu alguma coisa no sistema'. ... O Bus é o barramento CAN de um carro... O Bridge é o gateway que pega determinadas mensagens daquele barramento e manda para outra rede."

**Sobre BLE como transporte (doc2, ChatGPT, §13.5):**
> "BLE não seria uma funcionalidade especial da aplicação. Seria só mais um transporte do protocolo de eventos."

**Sobre a inversão do modelo de UI (doc2, §19):** a analogia do próprio Elias — "praticamente como um jogo" — para descrever a Presentation Surface como scene montada em runtime.

**Sobre a decisão de abandonar dependência de A2UI (doc2, §20, citação em francês registrada no documento, referência a Édith Piaf):**
> "Je repars à zéro. Je ne regrette rien."

**Sobre a invariante estrutural (doc3, §1):**
> "Toda dDock possui uma PresentationLayer."
> "A PresentationLayer é definida por sua função arquitetural, não pela tecnologia visual usada."

**Sobre a regra de ouro dos eventos (doc3, §14):**
> "O evento sobe de escopo somente quando seu significado sobe de escopo."

**Sobre a classificação required/optional (doc3, §20):**
> "`transparentBackground` não é, por natureza, obrigatório nem opcional. É a Surface que determina a força daquela exigência."

**Sobre o Talking Dinosaur Test (doc3, §19):**
> "O dinossauro falante consegue interpretar isso de alguma forma coerente?"

**Sobre a tese final da unidade universal Tile (doc2, §43, fechamento):**
> "Tile aparece como a unidade espacial que faltava para transformar interoperabilidade de apresentação em algo concreto: a mesma informação pode se materializar de forma mínima ou rica conforme a Surface, de um display monocromático barato a um videowall, sem obrigar a existência de páginas ou aplicações visuais diferentes para cada dispositivo."

**Sobre navegação como recência (doc2, §34):**
> "topo = agora; abaixo = recentemente; mais abaixo = passado ainda acessível."

---

## Observações finais

1. **Terminologia cunhada** (glossário para referência rápida): `dDock`, `Dock`/`dDock` (infra de eventos), `PresentationLayer`, `Presentation Surface`, `Tile` (vs `Component`), `Presentation Event Bus`, `Component Event` / `Presentation Global Event` / `External Event`, `Event Bridge`, `Agent` (conhece domínio), `store-and-forward semântico`, `Talking Dinosaur Test`, `PresentationCapacity`, `TilePresentationRequest` (`required`/`optional`/`extra`), `Presentation Profile`, `Grid/Slot Engine`, `Presentation System Log`, `Context` (working set persistido).

2. **O que está sólido/decidido:** separação de papéis (Agent/Dock/Bridge/Bus/PresentationLayer/Surface/Tile/Component); os três escopos de evento e regra de promoção; blocos required/optional/extra na negociação Surface↔Tile; capacidades espaciais mínimas do Tile no browser; Talking Dinosaur Test como salvaguarda de generalidade; BLE como transporte de eventos (não feature especial); Dock sem inteligência de domínio.

3. **O que está explicitamente em aberto** (útil para priorizar o que ainda precisa ser decidido): protocolo de descoberta de capabilities do Tile (síncrono/declarativo/por evento); schema formal versionado do `TilePresentationRequest`; taxonomia de themes e representação de cores/fontes; contrato de identidade/permissões dentro de `extra`; lifecycle completo do Tile; algoritmo de packing/reflow da Surface; regras exatas de recência/pin/compactação; protocolo de pareamento BLE (hoje só há advertising unidirecional, sem handshake formal descrito); como múltiplas PresentationLayers coexistem numa mesma dDock.

4. O protótipo HTML `ontobdc/lab/presentation-tile/index.html` (com `onto-tile.present(request)` e eventos `tile-presented`/`tile-presentation-failed`) corresponde exatamente à implementação do contrato descrito na seção 20–31 do doc3 — é a primeira materialização concreta e deliberadamente restrita ao "primeiro alvo de implementação: navegador offline" (doc3 §18), com o aviso explícito de que decisões ali tomadas (grid em `columns×rows`, pixels CSS) não devem ser promovidas ao contrato universal sem passar pelo Talking Dinosaur Test.
