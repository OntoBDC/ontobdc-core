from ontobdc.view.domain.port.work_stream_script_machine import (
    WorkStreamScriptGenerationProcessStatePort,
)


class WorkStreamScriptGenerationProcessState(WorkStreamScriptGenerationProcessStatePort):
    """Cumulative states of the WorkStream Page's split runtime JS assets.

    Each state (after UNDEFINED) corresponds to one file written under
    `.__ontobdc__/asset/work_stream_view/` inside the container — the
    former `work_stream_view.js` monolith, split by responsibility, one
    file per state, generated via `ontobdc_view.work_stream_script_source`.
    """

    UNDEFINED = "__undefined__"
    VENDOR_SHEET_JS_ASSET_GENERATED = "__vendor_sheet_js_asset_generated__"
    I18N_SCRIPT_GENERATED = "__i18n_script_generated__"
    GRAPH_READER_SCRIPT_GENERATED = "__graph_reader_script_generated__"
    CSV_PREVIEW_SCRIPT_GENERATED = "__csv_preview_script_generated__"
    CONTAINER_CONNECTION_SCRIPT_GENERATED = "__container_connection_script_generated__"
    CONNECTION_STATE_SCRIPT_GENERATED = "__connection_state_script_generated__"
    CHROME_CONTROLS_SCRIPT_GENERATED = "__chrome_controls_script_generated__"
    ANNOTATION_BRIDGE_SCRIPT_GENERATED = "__annotation_bridge_script_generated__"
    PYODIDE_RUNTIME_SCRIPT_GENERATED = "__pyodide_runtime_script_generated__"
    LINKSET_OPERATIONS_SCRIPT_GENERATED = "__linkset_operations_script_generated__"
    FILE_CATEGORY_SCRIPT_GENERATED = "__file_category_script_generated__"
    DIMENSION_CARD_SCRIPT_GENERATED = "__dimension_card_script_generated__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.VENDOR_SHEET_JS_ASSET_GENERATED: "Vendored SheetJS Asset Generated",
                self.I18N_SCRIPT_GENERATED: "i18n Script Generated",
                self.GRAPH_READER_SCRIPT_GENERATED: "Graph Reader Script Generated",
                self.CSV_PREVIEW_SCRIPT_GENERATED: "CSV Preview Script Generated",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "Container Connection Script Generated",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "Connection State Script Generated",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "Chrome Controls Script Generated",
                self.ANNOTATION_BRIDGE_SCRIPT_GENERATED: "Annotation Bridge Script Generated",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "Pyodide Runtime Script Generated",
                self.LINKSET_OPERATIONS_SCRIPT_GENERATED: "Linkset Operations Script Generated",
                self.FILE_CATEGORY_SCRIPT_GENERATED: "File Category Script Generated",
                self.DIMENSION_CARD_SCRIPT_GENERATED: "Dimension Card Script Generated",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.VENDOR_SHEET_JS_ASSET_GENERATED: "Biblioteca SheetJS Materializada",
                self.I18N_SCRIPT_GENERATED: "Script de i18n Gerado",
                self.GRAPH_READER_SCRIPT_GENERATED: "Script de Leitura do Grafo Gerado",
                self.CSV_PREVIEW_SCRIPT_GENERATED: "Script de Pre-visualizacao de CSV Gerado",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "Script de Conexao de Pasta Gerado",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "Script de Estado de Conexao Gerado",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "Script de Controles do Chrome Gerado",
                self.ANNOTATION_BRIDGE_SCRIPT_GENERATED: "Script de Ponte de Anotacoes Gerado",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "Script de Runtime do Pyodide Gerado",
                self.LINKSET_OPERATIONS_SCRIPT_GENERATED: "Script de Operacoes de Linkset Gerado",
                self.FILE_CATEGORY_SCRIPT_GENERATED: "Script de Categoria de Arquivo Gerado",
                self.DIMENSION_CARD_SCRIPT_GENERATED: "Script de Card de Dimensao Gerado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No work_stream_view runtime script has been generated yet.",
                self.I18N_SCRIPT_GENERATED: "i18n_apply.js was generated: applies [data-i18n]/[data-i18n-title]/[data-i18n-aria-label] chrome translations.",
                self.GRAPH_READER_SCRIPT_GENERATED: "graph_reader.js was generated: reads the embedded JSON-LD graph (loadGraph, literal, nodeTypes, resourceNodes, resourceLabel, resourceMimeKind, renderHeader).",
                self.CSV_PREVIEW_SCRIPT_GENERATED: "csv_preview.js was generated: parses and renders CSV resource previews without depending on pyodide.",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "container_connection.js was generated: File System Access API + IndexedDB folder connection (isContainerHandle, resolveContainerHandle, acquireContainerHandle, openContainer).",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "connection_state.js was generated: connect-button state transitions (setConnected, setConnectError, tryReconnectSilently) that never paint a fake connected state.",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "chrome_controls.js was generated: wires the Page header chrome (connect-btn click listener, status dot indicator, refresh/workspace/subjects buttons, i18n label helper) plus the wireAnnotationControls alias required by dimension_card.js backward compatibility. Shared with Gantt.",
                self.ANNOTATION_BRIDGE_SCRIPT_GENERATED: "annotation_bridge.js was generated: bridges to the native ontobdc OntoBDCAnnotations runtime.",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "pyodide_runtime.js was generated: Pyodide bootstrap and the WORKBOOK_PARSE_SCRIPT embedded Python parse.",
                self.LINKSET_OPERATIONS_SCRIPT_GENERATED: "linkset_operations.js was generated: relate/unrelate/suggest ICDD DirectedBinaryLink operations, generalized by linkset kind.",
                self.FILE_CATEGORY_SCRIPT_GENERATED: "file_category.js was generated: classifies resources into display categories from file_display.ttl, in pure JS.",
                self.DIMENSION_CARD_SCRIPT_GENERATED: "dimension_card.js was generated: builds each 5W2H dimension card's DOM and wires the page's render() bootstrap.",
            },
            "pt-br": {
                self.UNDEFINED: "Nenhum script de runtime do work_stream_view foi gerado ainda.",
                self.I18N_SCRIPT_GENERATED: "i18n_apply.js foi gerado: aplica traducoes de chrome [data-i18n]/[data-i18n-title]/[data-i18n-aria-label].",
                self.GRAPH_READER_SCRIPT_GENERATED: "graph_reader.js foi gerado: le o grafo JSON-LD incorporado (loadGraph, literal, nodeTypes, resourceNodes, resourceLabel, resourceMimeKind, renderHeader).",
                self.CSV_PREVIEW_SCRIPT_GENERATED: "csv_preview.js foi gerado: parseia e renderiza pre-visualizacoes de CSV sem depender do pyodide.",
                self.CONTAINER_CONNECTION_SCRIPT_GENERATED: "container_connection.js foi gerado: conexao de pasta via File System Access API + IndexedDB (isContainerHandle, resolveContainerHandle, acquireContainerHandle, openContainer).",
                self.CONNECTION_STATE_SCRIPT_GENERATED: "connection_state.js foi gerado: transicoes de estado do botao de conexao (setConnected, setConnectError, tryReconnectSilently) que nunca pintam um estado de conectado falso.",
                self.CHROME_CONTROLS_SCRIPT_GENERATED: "chrome_controls.js foi gerado: conecta o chrome do cabecalho da Page (listener de click no connect-btn, indicador ponto de status, botoes refresh/workspace/subjects, helper de rotulo i18n) mais o alias wireAnnotationControls exigido pela compatibilidade retroativa do dimension_card.js. Compartilhado com Gantt.",
                self.ANNOTATION_BRIDGE_SCRIPT_GENERATED: "annotation_bridge.js foi gerado: ponte para o runtime nativo OntoBDCAnnotations do ontobdc.",
                self.PYODIDE_RUNTIME_SCRIPT_GENERATED: "pyodide_runtime.js foi gerado: bootstrap do Pyodide e o parse Python embutido WORKBOOK_PARSE_SCRIPT.",
                self.LINKSET_OPERATIONS_SCRIPT_GENERATED: "linkset_operations.js foi gerado: operacoes de relacionar/desrelacionar/sugerir do linkset ICDD DirectedBinaryLink, generalizadas por tipo de linkset.",
                self.FILE_CATEGORY_SCRIPT_GENERATED: "file_category.js foi gerado: classifica recursos em categorias de exibicao a partir do file_display.ttl, em JS puro.",
                self.DIMENSION_CARD_SCRIPT_GENERATED: "dimension_card.js foi gerado: monta o DOM de cada card de dimensao 5W2H e conecta o bootstrap render() da pagina.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "WorkStreamScriptGenerationProcessState":
        return getattr(WorkStreamScriptGenerationProcessState, state.upper())
