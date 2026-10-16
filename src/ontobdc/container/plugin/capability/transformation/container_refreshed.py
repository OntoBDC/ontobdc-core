from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateEvaluatorAdapter,
    ContainerRefreshStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshStateTransitionHandlerPort,
)
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState


class ContainerRefreshedCapability(TransactionCapability):
    """
    Refreshes the local container that holds the downloaded remote files,
    by running the same container-refresh machine a local container goes
    through.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_refreshed"
        ),
        version="1.0.0",
        name="Container Refreshed",
        description=(
            "Refresh the local OntoBDC Container that holds the downloaded "
            "remote files."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "remote", "refresh"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The local container for the remote files was refreshed.",
            },
            "debug_entry": {
                "en": "Refreshing the local container for the remote files.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_REFRESHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_REFRESHED.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        context.set_parameter_value(
            "container_path", str(self._container_path(context))
        )
        evaluator: ContainerRefreshStateEvaluatorAdapter = ContainerRefreshStateEvaluatorAdapter()

        return (
            evaluator.evaluate(context) == ContainerRefreshProcessState.CONTAINER_UPDATED
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = self._container_path(context)
        context.set_parameter_value("container_path", str(container_path))

        handler: ContainerRefreshStateTransitionHandlerPort = (
            ContainerRefreshStateTransitionHandler(context=context)
        )
        response: CommandResponse = handler.execute()

        return {
            "resulting_state": RemoteContainerProcessState.CONTAINER_REFRESHED,
            "container_path": str(container_path),
            **(response.content or {}),
        }

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        container_path: Any = context.get_parameter_value("container_path")
        if isinstance(container_path, str) and container_path.strip():
            return Path(container_path)

        url: Any = context.get_parameter_value("remote_url")
        download_dir: Any = context.get_parameter_value("remote_download_dir")
        return RemoteContainerUrl.destination(url, download_dir).parent
