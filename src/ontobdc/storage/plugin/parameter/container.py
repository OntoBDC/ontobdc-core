
import os
from pathlib import Path
from typing import Callable, Optional
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort
from ontobdc.shared.domain.port.old_repository import LoadedStorageGraphPort
from ontobdc.cli.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort, PromptChoiceAwarePort


class ContainerIdStrategy(ParameterPort, CliContextStrategyPort, PromptChoiceAwarePort, LoggerAwarePort):
    """
    Strategy metadata for resolving a storage container input.
    """

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.storage.capability.incoming.container",
        version="0.1.0",
        name="container_id",
        description="Container repository instance to resolve the target container to use.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=ContainerRepositoryPort,
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
        # If the context already has the parameter explicitly passed via command line, don't overwrite it
        if context.has_parameter("container_id"):
            return context

        container_id = ContainerIdStrategy._infer_container_id_from_current_path()
        if container_id:
            context.set_parameter_value("container_id", container_id)

        return context

    @staticmethod
    def _infer_container_id_from_current_path() -> Optional[str]:
        current_working_directory: Path = Path(os.getcwd()).resolve()
        storage_file: str = get_storage_file()
        if not os.path.isfile(storage_file):
            return None

        try:
            storage_graph: LoadedStorageGraphPort = LoadedStorageGraph(storage_file)
            for subject, container_config_dir, _ in storage_graph.containers:
                container_root_path: Path = Path(container_config_dir).parent.resolve()
                if current_working_directory.is_relative_to(container_root_path):
                    return str(subject)
        except Exception:
            return None

        return None
