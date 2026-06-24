
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
        # Try to infer dataset from current working directory
        cwd = Path(os.getcwd())
        storage_file = get_storage_file()
        
        if os.path.isfile(storage_file):
            try:
                storage_graph = LoadedStorageGraph(storage_file)
                # First attempt to find the dataset using the current directory path directly
                dataset = storage_graph.get_dataset(dataset_location=cwd.as_uri())
                if dataset is None:
                    dataset = storage_graph.get_dataset(dataset_location=str(cwd))
                
                # If not found directly, iterate upwards through the parents
                if dataset is None:
                    for parent in cwd.parents:
                        dataset = storage_graph.get_dataset(dataset_location=parent.as_uri())
                        if dataset is None:
                            dataset = storage_graph.get_dataset(dataset_location=str(parent))
                        if dataset is not None:
                            break
                            
                if dataset is not None:
                    context.set_parameter_value("dataset_id", dataset)
                    # Infer container implicitly when we infer dataset
                    if not context.has_parameter("container_id") and dataset.container:
                        from ontobdc.storage.adapter.container import StorageContainerAdapter
                        container_repository = StorageContainerAdapter(storage_graph, dataset.container)
                        context.set_parameter_value("container_id", container_repository)
                        
                    if self._log_strategy:
                        self._log_strategy.print_log("INFO", "Context", f"Inferred dataset '{dataset.id}' from current directory.")
            except Exception:
                pass
                
        return context