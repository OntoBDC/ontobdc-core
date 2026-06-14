from typing import Callable, Optional

from ontobdc.storage.domain.port.repository import ContainerRepositoryPort
from ontobdc.shared.domain.port.context import CliContextPort, CliContextStrategyPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.shared.domain.resource.param import Parameter, ParameterMetadata


class ContainerIdStrategy(Parameter, CliContextStrategyPort, PromptChoiceAwarePort, LoggerAwarePort):
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
        return context
