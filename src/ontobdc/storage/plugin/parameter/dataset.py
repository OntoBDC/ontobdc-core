
from ontobdc.shared.domain.resource.param import Parameter, ParameterMetadata
from rdflib import URIRef
from typing import Any, Dict, List, Optional, Callable
from ontobdc.storage import get_storage_file
from ontobdc.storage.domain.port.dataset import DatasetRepositoryPort
from ontobdc.shared.domain.port.context import CliContextPort, CliContextStrategyPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from rdflib.namespace import DCTERMS, PROV, RDF
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix


class DatasetIdStrategy(Parameter, CliContextStrategyPort, PromptChoiceAwarePort, LoggerAwarePort):
    """
    DatasetIdStrategy is a strategy to resolve dataset id.
    """
    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.storage.capability.incoming.dataset",
        version="0.1.0",
        name="dataset_id",
        description="Dataset repository instance to resolve the id of the dataset to use.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=DatasetRepositoryPort,
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[Callable] = None

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: Callable):
        self._prompt_choice = prompt_choice

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        return self._log_strategy

    def execute(self, context: CliContextPort) -> CliContextPort:
        pass