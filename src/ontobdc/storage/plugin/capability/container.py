from typing import Any, Dict, List, Optional

from ontobdc.storage.adapter.container import StorageContainerAdapter
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort
from rdflib import Graph
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.shared.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.shared.domain.resource.capability import CapabilityMetadata, QueryCapability

CT = get_ontology_by_prefix("ct")


class SelectContainerCapability(QueryCapability, LoggerAwarePort, PromptChoiceAwarePort):
    """
    Resolve a storage container by prompting the user to select one.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.storage.capability.query.container",
        version="0.1.0",
        name="Select Container",
        description="Resolve a storage container by prompting the user to choose one of the registered containers.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["storage", "container", "selection", "query"],
            "pt": ["storage", "container", "selecao", "consulta"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {},
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.storage.capability.incoming.container": {
                    "type": ContainerRepositoryPort,
                    "uri": "org.ontobdc.domain.storage.capability.incoming.container",
                    "description": "Selected storage container repository instance.",
                }
            },
        },
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[callable] = None

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, str] = {
            "en": "Select Container",
            "pt": "Selecionar Container",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, str] = {
            "en": "Prompt the user to select one registered storage container.",
            "pt": "Mostra um prompt para selecionar um container registrado.",
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
            "en": "Select a container",
            "pt": "Selecione um container",
        }
        return prompts.get(lang, prompts["en"])

    def _cancel_label(self, lang: str) -> str:
        labels: Dict[str, str] = {
            "en": "Cancel",
            "pt": "Cancelar",
        }
        return labels.get(lang, labels["en"])

    def _all_containers(self) -> List[Dict[str, Any]]:
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        graph: Graph = storage_graph.graph
        containers: List[Dict[str, Any]] = []

        for container_ref in graph.subjects(RDF.type, CT.ContainerDescription):
            container_id: Optional[str] = None
            for identifier in graph.objects(container_ref, DCTERMS.identifier):
                container_id = str(identifier).strip()
                break

            if not isinstance(container_id, str) or not container_id or container_id == "urn:ontobdc:storage/local":
                continue

            title: Optional[str] = None
            for container_title in graph.objects(container_ref, DCTERMS.title):
                title = str(container_title).strip()
                break

            location: Optional[str] = None
            for container_location in graph.objects(container_ref, PROV.atLocation):
                location = str(container_location).strip()
                break

            containers.append(
                {
                    "id": container_id,
                    "title": title,
                    "location": location,
                }
            )

        containers.sort(key=lambda item: str(item.get("id", "")))
        return containers

    def _choice_label(self, container: Dict[str, Any]) -> str:
        title: str = str(container.get("title", "")).strip()
        container_id: str = str(container.get("id", "")).strip()
        location: str = str(container.get("location", "")).strip()

        if title:
            return f"{title} ({container_id})"

        if location:
            return f"{container_id} [{location}]"

        return container_id

    def _choice_value(self, container: Dict[str, Any]) -> str:
        return str(container.get("id", "")).strip()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if self._prompt_choice is None:
            raise RuntimeError("Prompt choice function is not configured.")

        containers: List[Dict[str, Any]] = self._all_containers()
        if len(containers) == 0:
            raise ValueError("No registered containers were found.")

        language: str = self._normalized_language(context)
        choice_options: List[str] = [self._choice_label(container) for container in containers]
        choice_values: List[str] = [self._choice_value(container) for container in containers]
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
            raise RuntimeError("Container selection was canceled by the user.")

        selected_index: int = choice_values.index(selected_value)
        selected_container: Dict[str, Any] = containers[selected_index]
        selected_container_id: str = str(selected_container.get("id", "")).strip()
        if not selected_container_id:
            raise ValueError("The selected container does not define a valid identifier.")

        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
        selected_container_repository: ContainerRepositoryPort = StorageContainerAdapter(
            storage_graph,
            selected_container_id,
        )

        return {
            "org.ontobdc.domain.storage.capability.incoming.container": selected_container_repository,
        }
