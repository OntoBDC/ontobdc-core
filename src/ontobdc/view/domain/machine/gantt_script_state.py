from ontobdc.view.domain.port.gantt_script_machine import (
    GanttScriptGenerationProcessStatePort,
)


class GanttScriptGenerationProcessState(GanttScriptGenerationProcessStatePort):
    """Cumulative states of the Gantt Page's split runtime JS assets.

    Each state (after UNDEFINED) corresponds to one file written under
    `.__ontobdc__/asset/ifc_work_schedule_view/` inside the container — the
    former `ifc_work_schedule_view.js` monolith, split by responsibility, one
    file per state, generated via `ontobdc_view.gantt_script_source`.
    """

    UNDEFINED = "__undefined__"
    I18N_SCRIPT_GENERATED = "__i18n_script_generated__"
    GRAPH_READER_SCRIPT_GENERATED = "__graph_reader_script_generated__"
    CONTAINER_CONNECTION_SCRIPT_GENERATED = "__container_connection_script_generated__"
    CONNECTION_STATE_SCRIPT_GENERATED = "__connection_state_script_generated__"
    CHROME_CONTROLS_SCRIPT_GENERATED = "__chrome_controls_script_generated__"
    PYODIDE_RUNTIME_SCRIPT_GENERATED = "__pyodide_runtime_script_generated__"
    TASK_TABLE_TIMELINE_SCRIPT_GENERATED = "__task_table_timeline_script_generated__"
    DEPENDENCY_ARROWS_SCRIPT_GENERATED = "__dependency_arrows_script_generated__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.I18N_SCRIPT_GENERATED: "i18n Script Generated",
                self.GRAPH_READER_SCRIPT_GENERATED: "Graph Reader Script Generated",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "Container Connection Script Generated",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "Connection State Script Generated",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "Chrome Controls Script Generated",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "Pyodide Runtime Script Generated",
                self.TASK_TABLE_TIMELINE_SCRIPT_GENERATED: "Task Table & Timeline Script Generated",
                self.DEPENDENCY_ARROWS_SCRIPT_GENERATED: "Dependency Arrows Script Generated",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.I18N_SCRIPT_GENERATED: "Script de i18n Gerado",
                self.GRAPH_READER_SCRIPT_GENERATED: "Script de Leitura do Grafo Gerado",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "Script de Conexao com o Container Gerado",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "Script de Estado da Conexao Gerado",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "Script de Controles do Chrome Gerado",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "Script de Runtime Pyodide Gerado",
                self.TASK_TABLE_TIMELINE_SCRIPT_GENERATED: "Script de Tabela de Tarefas e Timeline Gerado",
                self.DEPENDENCY_ARROWS_SCRIPT_GENERATED: "Script de Setas de Dependencia Gerado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No ifc_work_schedule_view runtime script has been generated yet.",
                self.I18N_SCRIPT_GENERATED: "i18n_apply.js was generated: applies [data-i18n]/[data-i18n-title]/[data-i18n-aria-label] chrome translations.",
                self.GRAPH_READER_SCRIPT_GENERATED: "graph_reader.js was generated: reads the embedded JSON-LD graph (IFC task types, literal/date parsers, enriched task list) and attaches everything to `window.OntoBDCGanttViewRuntime.state`.",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "container_connection.js was generated: acquires the container directory handle (picker, IndexedDB persistence across reloads, permission prompt, dataset-folder descent) through the runtime shared with the WorkStream Page.",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "connection_state.js was generated: reflects the connection status in the Page header and re-opens a previously connected folder on load.",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "chrome_controls.js was generated: wires the Page header chrome (connect-btn click listener that opens the directory picker, connection status dot indicator, refresh/workspace/subjects buttons, i18n label helper). Shared with WorkStream.",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "pyodide_runtime.js was generated: loads Pyodide with rdflib/openpyxl, mounts the connected folder and parses the schedule workbook into the Page's own JSON-LD graph, so the Gantt is drawn from the container's live spreadsheet rather than from build-time data.",
                self.TASK_TABLE_TIMELINE_SCRIPT_GENERATED: "task_table_timeline.js was generated: builds the left 6-column table (WBS/Name/Start/Finish/Duration/%), the SVG timeline grid, milestone diamonds, progress overlays, bar labels and left/right scroll sync.",
                self.DEPENDENCY_ARROWS_SCRIPT_GENERATED: "dependency_arrows.js was generated: walks the parsed IfcRelSequence edges and draws MS-Project-style SVG dependency arrows (horizontal + vertical + horizontal, arrowhead) — must run last because it depends on rendered bar geometries.",
            },
            "pt-br": {
                self.UNDEFINED: "Nenhum script de runtime do ifc_work_schedule_view foi gerado ainda.",
                self.I18N_SCRIPT_GENERATED: "i18n_apply.js foi gerado: aplica traducoes de chrome [data-i18n]/[data-i18n-title]/[data-i18n-aria-label].",
                self.GRAPH_READER_SCRIPT_GENERATED: "graph_reader.js foi gerado: le o grafo JSON-LD incorporado (tipos IFC de tarefa, parsers de literal/data, lista enriquecida de tarefas) e anexa tudo em `window.OntoBDCGanttViewRuntime.state`.",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "container_connection.js foi gerado: obtem o handle do diretorio do container (seletor, persistencia em IndexedDB entre reloads, permissao, descida ate a pasta do dataset) pelo runtime compartilhado com a Page do WorkStream.",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "connection_state.js foi gerado: reflete o status da conexao no cabecalho da Page e reabre uma pasta previamente conectada ao carregar.",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "chrome_controls.js foi gerado: conecta o chrome do cabecalho da Page (listener de click no connect-btn que abre o picker de diretorio, indicador de status ponto, botoes refresh/workspace/subjects, helper de rotulo i18n). Compartilhado com WorkStream.",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "pyodide_runtime.js foi gerado: carrega o Pyodide com rdflib/openpyxl, monta a pasta conectada e faz o parse da planilha do cronograma para o proprio grafo JSON-LD da Page, de modo que o Gantt e desenhado a partir da planilha viva do container e nao de dados de build.",
                self.TASK_TABLE_TIMELINE_SCRIPT_GENERATED: "task_table_timeline.js foi gerado: monta a tabela esquerda de 6 colunas (WBS/Nome/Inicio/Termino/Duracao/%), o grid SVG do timeline, diamantes de marco, overlays de progresso, rotulos das barras e sincronizacao de scroll esquerdo/direito.",
                self.DEPENDENCY_ARROWS_SCRIPT_GENERATED: "dependency_arrows.js foi gerado: percorre as arestas IfcRelSequence parseadas e desenha setas de dependencia SVG no estilo MS-Project (horizontal + vertical + horizontal, cabeca de seta) — deve rodar por ultimo pois depende das geometrias das barras ja renderizadas.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "GanttScriptGenerationProcessState":
        return getattr(GanttScriptGenerationProcessState, state.upper())
