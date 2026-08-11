from typing import Any, Dict

from ontobdc.storage.domain.port.machine import (
    ContainerCreateProcessStatePort,
    ContainerUpdateProcessStatePort,
    DatasetCreateProcessStatePort,
)


class ContainerCreateProcessState(ContainerCreateProcessStatePort):
    """
    Enum representing the possible states of the storage container creation process.
    """

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    DIRECTORY_READY = "__directory_ready__"
    CONTAINER_METADATA_READY = "__container_metadata_ready__"
    CONTAINER_STORAGE_INDEX_READY = "__container_storage_index_ready__"
    CONTAINER_MANIFEST_SYNCED = "__container_manifest_synced__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.INVALID_PATH: "Invalid Path",
                self.DIRECTORY_READY: "Directory Ready",
                self.CONTAINER_METADATA_READY: "Container Metadata Ready",
                self.CONTAINER_STORAGE_INDEX_READY: "Container Storage Index Ready",
                self.CONTAINER_MANIFEST_SYNCED: "Container Manifest Synced",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.INVALID_PATH: "Caminho Invalido",
                self.DIRECTORY_READY: "Diretorio Pronto",
                self.CONTAINER_METADATA_READY: "Metadados do Container Prontos",
                self.CONTAINER_STORAGE_INDEX_READY: "Indice de Storage do Container Pronto",
                self.CONTAINER_MANIFEST_SYNCED: "Manifesto do Container Sincronizado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the target container directory exists.",
                self.INVALID_PATH: "The target path points to an existing file and cannot be used as a container directory.",
                self.DIRECTORY_READY: "The target container directory exists and is ready for the next creation steps.",
                self.CONTAINER_METADATA_READY: "The container metadata file exists and contains a valid data container description without requiring datasets.",
                self.CONTAINER_STORAGE_INDEX_READY: "The storage index entry for the container matches the container metadata file and is synchronized.",
                self.CONTAINER_MANIFEST_SYNCED: "The container manifest file exists and lists all container files excluding marker and dataset directories.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da existencia do diretorio alvo do container.",
                self.INVALID_PATH: "O caminho alvo aponta para um arquivo existente e nao pode ser usado como diretorio de container.",
                self.DIRECTORY_READY: "O diretorio alvo do container existe e esta pronto para as proximas etapas da criacao.",
                self.CONTAINER_METADATA_READY: "O arquivo de metadados do container existe e contem uma descricao valida do data container sem exigir datasets.",
                self.CONTAINER_STORAGE_INDEX_READY: "A entrada do container no indice de storage esta sincronizada com o arquivo de metadados do container.",
                self.CONTAINER_MANIFEST_SYNCED: "O manifesto do container existe e lista todos os arquivos do container exceto diretorios de marker e datasets.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ContainerCreateProcessState":
        return getattr(ContainerCreateProcessState, state.upper())


class ContainerUpdateProcessState(ContainerUpdateProcessStatePort):
    """
    Enum representing the possible states of the storage container update process.
    """

    UNDEFINED = "__undefined__"
    CONTAINER_INVALID = "__container_invalid__"
    CONTAINER_HEALTHY = "__container_healthy__"
    CONTAINER_DATASETS_HEALTHY = "__container_datasets_healthy__"
    CONTAINER_CLEANED = "__container_cleaned__"
    CONTAINER_DATAPACKAGE_UPDATED = "__container_datapackage_updated__"
    CONTAINER_RO_CRATE_UPDATED = "__container_ro_crate_updated__"
    CONTAINER_HTML_VIEW_UPDATED = "__container_html_view_updated__"
    CONTAINER_UPDATED = "__container_updated__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_labels", {}),
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_descriptions", {}),
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "ContainerUpdateProcessState":
        return getattr(ContainerUpdateProcessState, state.upper())

    @staticmethod
    def _normalize_presentation_metadata(value: Any) -> Dict[str, str]:
        if isinstance(value, str):
            return {"en": value}
        if not isinstance(value, dict):
            return {}

        return {
            str(language).strip().lower().replace("_", "-"): str(text)
            for language, text in value.items()
            if str(language).strip() and text is not None
        }

    @staticmethod
    def _localized_presentation_metadata(
        values: Dict[str, str],
        lang: str,
        default: str,
    ) -> str:
        normalized_lang: str = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))


class DatasetCreateProcessState(DatasetCreateProcessStatePort):
    """
    Enum representing the possible states of the storage dataset creation process.
    """

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    DIRECTORY_READY = "__directory_ready__"
    DATASET_METADATA_READY = "__dataset_metadata_ready__"
    DATASET_CONTAINER_INDEX_READY = "__dataset_container_index_ready__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.INVALID_PATH: "Invalid Path",
                self.DIRECTORY_READY: "Directory Ready",
                self.DATASET_METADATA_READY: "Dataset Metadata Ready",
                self.DATASET_CONTAINER_INDEX_READY: "Dataset Container Index Ready",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.INVALID_PATH: "Caminho Invalido",
                self.DIRECTORY_READY: "Diretorio Pronto",
                self.DATASET_METADATA_READY: "Metadados do Dataset Prontos",
                self.DATASET_CONTAINER_INDEX_READY: "Indice do Dataset no Container Pronto",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the target dataset directory exists.",
                self.INVALID_PATH: "The target path points to an existing file and cannot be used as a dataset directory.",
                self.DIRECTORY_READY: "The target dataset directory exists and is ready for the next creation steps.",
                self.DATASET_METADATA_READY: "The dataset metadata file exists and contains a valid dataset description.",
                self.DATASET_CONTAINER_INDEX_READY: "The container metadata file contains the dataset entry and remains synchronized with the dataset metadata file.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da existencia do diretorio alvo do dataset.",
                self.INVALID_PATH: "O caminho alvo aponta para um arquivo existente e nao pode ser usado como diretorio de dataset.",
                self.DIRECTORY_READY: "O diretorio alvo do dataset existe e esta pronto para as proximas etapas da criacao.",
                self.DATASET_METADATA_READY: "O arquivo de metadados do dataset existe e contem uma descricao valida do dataset.",
                self.DATASET_CONTAINER_INDEX_READY: "O container.ttl contem a entrada do dataset e esta sincronizado com o dataset.ttl.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "DatasetCreateProcessState":
        return getattr(DatasetCreateProcessState, state.upper())
