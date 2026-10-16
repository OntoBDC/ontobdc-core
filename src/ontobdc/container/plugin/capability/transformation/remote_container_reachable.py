from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.obdc import StorageObdcRepository
from ontobdc.storage.domain.port.obdc import (
    StorageObdcRemoteModelPort,
    StorageObdcRepositoryPort,
)

from ontobdc.container.adapter.remote_access import RemoteAccessProbe
from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState


class RemoteContainerReachableCapability(TransactionCapability):
    """
    Reads and validates the downloaded ``.obdc`` file of a remote OntoBDC
    Container, confirming at least one address it publishes answers.

    Reachability is a terminal action, not a persisted fact: the machine
    always re-verifies it instead of treating a past success as still true.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "remote_container_reachable"
        ),
        version="1.0.0",
        name="Remote Container Reachable",
        description=(
            "Read the remote.ttl of the downloaded remote OntoBDC Container "
            "file and confirm at least one published address answers."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "remote", "obdc"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The information of the remote container is available.",
            },
            "debug_entry": {
                "en": "Reading the remote.ttl of the remote container file.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.REMOTE_CONTAINER_REACHABLE.label(lang)

    def description(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.REMOTE_CONTAINER_REACHABLE.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        url_value: Any = context.get_parameter_value("remote_url")
        if not isinstance(url_value, str) or not url_value.strip():
            raise ValueError("The remote container URL is missing from the command context.")

        path: Path = RemoteContainerUrl.destination(
            url_value.strip(), context.get_parameter_value("remote_download_dir")
        )

        repository: StorageObdcRepositoryPort = StorageObdcRepository()
        remote: StorageObdcRemoteModelPort = repository.read_remote(path)
        remote.validate()

        api_token: Any = context.get_parameter_value("remote_api_token")
        RemoteAccessProbe.probe_any_address(
            remote.addresses(), api_token if isinstance(api_token, str) else None
        )

        return {
            "resulting_state": RemoteContainerProcessState.REMOTE_CONTAINER_REACHABLE,
            "path": str(path),
            "triples": len(remote.graph),
        }
