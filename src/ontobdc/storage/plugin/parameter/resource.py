
from typing import Callable, Optional
from ontobdc.shared.domain.port.context import (
    CliContextPort,
    CliContextStrategyPort,
    PromptRawTextAwarePort,
)
from ontobdc.storage.domain.port.resource import ResourcePort
from ontobdc.shared.domain.resource.param import Parameter, ParameterMetadata
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort


class ResourcePathStrategy(Parameter, CliContextStrategyPort, PromptRawTextAwarePort, LoggerAwarePort):
    """
    Strategy metadata for resolving a storage resource path input.
    """
    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.storage.capability.incoming.resource.path",
        version="0.1.0",
        name="resource_path",
        description="File resource instance to resolve the local path of the resource to use.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=ResourcePort,
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_raw_text: Optional[Callable] = None

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_raw_text(self, prompt_raw_text: Callable[[str], str]):
        self._prompt_raw_text = prompt_raw_text

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        return self._log_strategy

    def execute(self, context: CliContextPort) -> CliContextPort:
        return context
