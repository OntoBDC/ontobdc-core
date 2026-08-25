from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.gantt_script_state import (
    GanttScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.gantt_script_common import script_path
from ontobdc.view.plugin.check.is_gantt_pyodide_runtime_script_generated.check import (
    main as check_gantt_pyodide_runtime_script_generated,
)


class GanttPyodideRuntimeScriptGeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.gantt_pyodide_runtime_script_generated",
        version="1.0.0",
        name="Gantt Pyodide Runtime Script Generated",
        description="pyodide_runtime.js loads Pyodide, mounts the connected folder and parses the schedule workbook into the Page's own JSON-LD graph.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "gantt", "ifc-workschedule", "script", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "pyodide_runtime.js was generated under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
            "debug_entry": {
                "en": "Generating pyodide_runtime.js under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.PYODIDE_RUNTIME_SCRIPT_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.PYODIDE_RUNTIME_SCRIPT_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_gantt_pyodide_runtime_script_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, "pyodide_runtime")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.gantt_script_source("pyodide_runtime")
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": GanttScriptGenerationProcessState.PYODIDE_RUNTIME_SCRIPT_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
