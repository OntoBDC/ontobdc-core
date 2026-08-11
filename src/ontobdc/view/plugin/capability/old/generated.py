from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.domain.machine.state import ContainerViewProcessState
from ontobdc.view.plugin.capability.dataset_views_generated import (
    DatasetViewsGeneratedCapability,
)
from ontobdc.view.plugin.capability.workstream_schedule_relations import (
    are_workstream_schedule_relations_materialized,
    materialize_workstream_schedule_relations,
)


class GeneratedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "generated"
        ),
        version="1.1.0",
        name="Generated",
        description=(
            "Confirm the standalone view after every dataset was materialized "
            "through its facade, its supported entity pages were regenerated, "
            "and WorkStream schedule relations were published."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "view",
            "container",
            "generation",
            "transformation",
            "workstream",
            "ifc-work-schedule",
        ],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerViewProcessState.GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerViewProcessState.GENERATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        dataset_views_generated = DatasetViewsGeneratedCapability()
        if not dataset_views_generated.is_satisfied(context):
            raise RuntimeError(
                "The dataset entity pages were not generated in the "
                "container view."
            )

        raw_container_path = context.get_parameter_value("container_path")
        container_path = (
            Path(str(raw_container_path or "").strip())
            .expanduser()
            .resolve()
        )
        if not container_path.is_dir():
            raise ValueError(
                "Container path is not an accessible directory: "
                f"{container_path}"
            )
        relation_result = materialize_workstream_schedule_relations(
            container_path
        )
        return {
            "resulting_state": ContainerViewProcessState.GENERATED,
            "container_path": str(container_path),
            "index_path": str(container_path / "index.html"),
            **relation_result,
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        if not DatasetViewsGeneratedCapability().is_satisfied(context):
            return False
        raw_container_path = context.get_parameter_value("container_path")
        normalized = str(raw_container_path or "").strip()
        if not normalized:
            return False
        container_path = Path(normalized).expanduser().resolve()
        return (
            container_path.is_dir()
            and are_workstream_schedule_relations_materialized(
                container_path
            )
        )
