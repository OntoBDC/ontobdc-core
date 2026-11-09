from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.adapter.constraint_replication import ConstraintReplication
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ContainerConstraintReplicatedCapability(TransactionCapability):
    """Replicate the constraints of the application, given as the body of the config, into the config of the container."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_constraint_replicated"
        ),
        version="1.0.0",
        name="Container Constraints Replicated",
        description=(
            "Put the constraints of the application config, given with --config, in the config of the "
            "container, replacing what it held."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "refresh", "config", "constraint"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The constraints of the application were replicated into the config of the container."},
            "debug_entry": {"en": "Replicating the constraints of the application into the config of the container."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_CONSTRAINT_REPLICATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_CONSTRAINT_REPLICATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        written: bool = ConstraintReplication.replicate(
            str(context.root_path),
            RequiredParameter.optional(context, "config"),
        )

        return {
            "resulting_state": ContainerRefreshProcessState.CONTAINER_CONSTRAINT_REPLICATED,
            "replicated": written,
        }
