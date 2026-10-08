from ontobdc.container.plugin.machine.entity_write.port import (
    EntityWriteProcessStatePort,
)


class EntityWriteProcessState(EntityWriteProcessStatePort):
    """
    Enum representing the possible states of the writing of entities into
    the data source of a dataset.
    """

    UNDEFINED = "__undefined__"
    DATASET_FOUND = "__dataset_found__"
    DATA_SOURCE_AVAILABLE = "__data_source_available__"
    DATA_SOURCE_COLUMNS_SYNCED = "__data_source_columns_synced__"
    DATA_SOURCE_FILLED = "__data_source_filled__"
    ENTITY_DOCUMENTS_LINKED = "__entity_documents_linked__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.DATASET_FOUND: "Dataset Found",
                self.DATA_SOURCE_AVAILABLE: "Data Source Available",
                self.DATA_SOURCE_COLUMNS_SYNCED: "Data Source Columns Synced",
                self.DATA_SOURCE_FILLED: "Data Source Filled",
                self.ENTITY_DOCUMENTS_LINKED: "Entity Documents Linked",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.DATASET_FOUND: "Dataset Encontrado",
                self.DATA_SOURCE_AVAILABLE: "Fonte de Dados Disponivel",
                self.DATA_SOURCE_COLUMNS_SYNCED: "Colunas da Fonte de Dados Sincronizadas",
                self.DATA_SOURCE_FILLED: "Fonte de Dados Preenchida",
                self.ENTITY_DOCUMENTS_LINKED: "Documentos da Entidade Ligados",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the container has a dataset of the entity.",
                self.DATASET_FOUND: "The container has a dataset that holds the entity.",
                self.DATA_SOURCE_AVAILABLE: "The dataset has the data source of the entity.",
                self.DATA_SOURCE_COLUMNS_SYNCED: "The data source has a column for every field of the entity facade.",
                self.DATA_SOURCE_FILLED: "The data source holds the rows of the entities.",
                self.ENTITY_DOCUMENTS_LINKED: "The dataset linkset ties the data source to the documents the entities were made on.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes de o container ter um dataset da entidade.",
                self.DATASET_FOUND: "O container tem um dataset que contem a entidade.",
                self.DATA_SOURCE_AVAILABLE: "O dataset tem a fonte de dados da entidade.",
                self.DATA_SOURCE_COLUMNS_SYNCED: "A fonte de dados tem uma coluna para cada campo da facade da entidade.",
                self.DATA_SOURCE_FILLED: "A fonte de dados contem as linhas das entidades.",
                self.ENTITY_DOCUMENTS_LINKED: "O linkset do dataset liga a fonte de dados aos documentos sobre os quais as entidades foram feitas.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "EntityWriteProcessState":
        return getattr(EntityWriteProcessState, state.upper())
