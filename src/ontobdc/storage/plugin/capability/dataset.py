from typing import Any, Dict, List, Optional

from rdflib import URIRef

from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort
from ontobdc.storage.domain.port.dataset import DatasetRepositoryPort
from ontobdc.shared.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.shared.domain.resource.capability import CapabilityMetadata, QueryCapability


class SelectDatasetCapability(QueryCapability, LoggerAwarePort, PromptChoiceAwarePort):
    """
    Resolve a dataset from a known container by prompting the user to select one.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.storage.capability.query.dataset",
        version="0.1.0",
        name="Select Dataset",
        description="Resolve a dataset repository from a container repository by prompting the user to choose a dataset.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["storage", "dataset", "selection", "query"],
            "pt": ["storage", "dataset", "seleção", "consulta"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": ContainerRepositoryPort,
                    "uri": "org.ontobdc.domain.storage.capability.incoming.container",
                    "required": True,
                    "description": "Registered container repository instance used to filter datasets.",
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.storage.capability.incoming.dataset": {
                    "type": DatasetRepositoryPort,
                    "uri": "org.ontobdc.domain.storage.capability.incoming.dataset",
                    "description": "Selected dataset repository instance.",
                }
            },
        },
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[callable] = None

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, str] = {
            "en": "Select Dataset",
            "pt": "Selecionar Dataset",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, str] = {
            "en": "Prompt the user to select a dataset from a registered container.",
            "pt": "Mostra um prompt para selecionar um dataset de um container registrado.",
        }
        return descriptions.get(lang, descriptions["en"])

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: callable):
        self._prompt_choice = prompt_choice

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        return self._log_strategy

    def _normalized_language(self, context: CliContextPort) -> str:
        language: Optional[str] = context.language
        if isinstance(language, str) and language.strip():
            return language.split("-")[0].split("_")[0]
        return "en"

    def _prompt_text(self, lang: str) -> str:
        prompts: Dict[str, str] = {
            "en": "Select a dataset",
            "pt": "Selecione um dataset",
        }
        return prompts.get(lang, prompts["en"])

    def _cancel_label(self, lang: str) -> str:
        labels: Dict[str, str] = {
            "en": "Cancel",
            "pt": "Cancelar",
        }
        return labels.get(lang, labels["en"])

    def _choice_label(self, dataset: Dict[str, Any]) -> str:
        title: Any = dataset.get("title")
        if isinstance(title, dict):
            english_title: Optional[str] = title.get("en")
            if isinstance(english_title, str) and english_title.strip():
                return f"{english_title} ({dataset.get('@id', '')})"

            portuguese_title: Optional[str] = title.get("pt")
            if isinstance(portuguese_title, str) and portuguese_title.strip():
                return f"{portuguese_title} ({dataset.get('@id', '')})"

        location: str = str(dataset.get("location", "")).strip()
        if location:
            return f"{location} ({dataset.get('@id', '')})"

        return str(dataset.get("@id", "")).strip()

    def _choice_value(self, dataset: Dict[str, Any]) -> str:
        return str(dataset.get("@id", "")).strip()

    def _datasets_for_container(self, container_id: str) -> List[Dict[str, Any]]:
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        all_datasets: List[Dict[str, Any]] = storage_graph.get_all_datasets()

        return [
            dataset
            for dataset in all_datasets
            if str(dataset.get("container_id", "")).strip() == container_id
        ]

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if self._prompt_choice is None:
            raise RuntimeError("Prompt choice function is not configured.")

        container_value: Any = context.get_parameter_value("container_id")
        normalized_container_id: Optional[str] = None
        if isinstance(container_value, ContainerRepositoryPort):
            normalized_container_id = container_value.id.strip()
        elif isinstance(container_value, str) and container_value.strip():
            normalized_container_id = container_value.strip()

        if not isinstance(normalized_container_id, str) or not normalized_container_id:
            raise ValueError("container_id is required to resolve a dataset.")

        datasets: List[Dict[str, Any]] = self._datasets_for_container(normalized_container_id)
        if len(datasets) == 0:
            raise ValueError(f"No datasets found for container '{normalized_container_id}'.")

        language: str = self._normalized_language(context)
        choice_options: List[str] = [self._choice_label(dataset) for dataset in datasets]
        choice_values: List[str] = [self._choice_value(dataset) for dataset in datasets]
        cancel_label: str = self._cancel_label(language)

        selected_value: str = self._prompt_choice(
            "Storage",
            self._prompt_text(language),
            choice_options,
            default=choice_options[0],
            language=language,
            none=cancel_label,
        )

        if selected_value == cancel_label:
            raise RuntimeError("Dataset selection was canceled by the user.")

        selected_index: int = choice_values.index(selected_value)
        selected_dataset: Dict[str, Any] = datasets[selected_index]
        dataset_ref: URIRef = URIRef(str(selected_dataset.get("@ref") or selected_dataset.get("@id")))

        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        dataset_repository: Optional[DatasetRepositoryPort] = storage_graph.get_dataset(dataset_ref=dataset_ref)
        if dataset_repository is None:
            raise ValueError(f"Dataset '{dataset_ref}' could not be loaded.")

        return {
            "org.ontobdc.domain.storage.capability.incoming.dataset": dataset_repository,
        }
