from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.plugin.machine.container_create.machine import (
    ContainerCreateStateEvaluatorAdapter,
    ContainerCreateStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateStateTransitionHandlerPort,
)
from ontobdc.container.plugin.machine.container_create.state import ContainerCreateProcessState
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState


class ContainerCreatedCapability(TransactionCapability):
    """
    Creates the local container that holds the downloaded remote file, by
    running the same container-create machine a local container goes
    through.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_created"
        ),
        version="1.0.0",
        name="Container Created",
        description=(
            "Create the local OntoBDC Container that holds the downloaded "
            "remote file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "remote", "create"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The local container for the remote file was created.",
            },
            "debug_entry": {
                "en": "Creating the local container for the remote file.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_CREATED.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        context.set_parameter_value(
            "container_path", str(self._container_path(context))
        )
        evaluator: ContainerCreateStateEvaluatorAdapter = ContainerCreateStateEvaluatorAdapter()

        return (
            evaluator.evaluate(context) == ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = self._container_path(context)
        context.set_parameter_value("container_path", str(container_path))

        handler: ContainerCreateStateTransitionHandlerPort = (
            ContainerCreateStateTransitionHandler(context=context)
        )
        response: CommandResponse = handler.execute()

        return {
            "resulting_state": RemoteContainerProcessState.CONTAINER_CREATED,
            "container_path": str(container_path),
            **(response.content or {}),
        }

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        url: Any = context.get_parameter_value("remote_url")
        download_dir: Any = context.get_parameter_value("remote_download_dir")

        return RemoteContainerUrl.destination(url, download_dir).parent
