from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.plugin.capability.transformation.container_healthy import ContainerHealthyCapability
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ContainerHotfixedCapability(TransactionCapability):
    """
    Makes sure the container is healthy, and repairs it when it is not, the way the refresh of a container does.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.container_hotfixed",
        version="1.0.0",
        name="Container Hotfixed",
        description="Make sure the container is healthy, and repair it when it is not.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "container", "hotfix"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The container is healthy."},
            "debug_entry": {"en": "Checking the container."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.CONTAINER_HOTFIXED.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.CONTAINER_HOTFIXED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        healthy: ContainerHealthyCapability = ContainerHealthyCapability()
        repaired: bool = not healthy.check(context)
        if repaired:
            healthy.execute(context)
            if not healthy.check(context):
                raise RuntimeError("The container is still not healthy after the repair.")

        return {"resulting_state": JobCreateProcessState.CONTAINER_HOTFIXED, "repaired": repaired}
