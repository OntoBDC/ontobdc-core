from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.gantt_script_state import (
    GanttScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.gantt_script_common import script_path
from ontobdc.view.plugin.check.is_gantt_dependency_arrows_script_generated.check import (
    main as check_gantt_dependency_arrows_script_generated,
)


class GanttDependencyArrowsScriptGeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.gantt_dependency_arrows_script_generated",
        version="1.0.0",
        name="Gantt Dependency Arrows Script Generated",
        description="dependency_arrows.js draws MS-Project-style SVG IfcRelSequence dependency arrows (horizontal + vertical + horizontal path) — final state because it depends on rendered bar geometries.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "gantt", "ifc-workschedule", "ifc-rel-sequence", "script", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "dependency_arrows.js was generated under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
            "debug_entry": {
                "en": "Generating dependency_arrows.js under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.DEPENDENCY_ARROWS_SCRIPT_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.DEPENDENCY_ARROWS_SCRIPT_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_gantt_dependency_arrows_script_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, "dependency_arrows")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.gantt_script_source("dependency_arrows")
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": GanttScriptGenerationProcessState.DEPENDENCY_ARROWS_SCRIPT_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
