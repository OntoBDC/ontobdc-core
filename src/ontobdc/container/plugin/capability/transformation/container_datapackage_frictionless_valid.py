from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_container_datapackage_frictionless_valid,
)
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.hotfix import (
    main as hotfix_container_datapackage_frictionless_valid,
)


class ContainerDataPackageFrictionlessValidCapability(TransactionCapability):
    """Prune datapackage.json resources whose format isn't frictionless-compatible."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_datapackage_frictionless_valid"
        ),
        version="1.0.0",
        name="Container Data Package Frictionless Valid",
        description=(
            "Remove Data Package resources whose format frictionless doesn't "
            "treat as structured/tabular data."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "datapackage", "frictionless"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Non-tabular resources unsupported by Frictionless were removed "
                    "from the Data Package descriptor."
                ),
            },
            "debug_entry": {
                "en": (
                    "Removing non-tabular resources unsupported by "
                    "Frictionless from the Data Package descriptor."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        container_path_str: str = str(container_path)
        root_path: str = str(context.root_path).strip()

        if check_container_datapackage_frictionless_valid(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            if hotfix_container_datapackage_frictionless_valid(
                container_path=container_path_str,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container Data Package frictionless compatibility."
                )

        if check_container_datapackage_frictionless_valid(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package still has non-frictionless-compatible "
                "resources after the hotfix."
            )

        return {
            "resulting_state": (
                ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED
            ),
            "container_path": container_path_str,
        }
