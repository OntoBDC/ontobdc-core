from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.gantt_script_state import (
    GanttScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.gantt_script_common import script_path
from ontobdc.view.plugin.check.is_gantt_i18n_script_generated.check import (
    main as check_gantt_i18n_script_generated,
)


class GanttI18nScriptGeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.gantt_i18n_script_generated",
        version="1.0.0",
        name="Gantt i18n Script Generated",
        description="i18n_apply.js applies chrome-level [data-i18n] translations and initializes the shared OntoBDCGanttViewRuntime namespace.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "gantt", "ifc-workschedule", "script", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "i18n_apply.js was generated under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
            "debug_entry": {
                "en": "Generating i18n_apply.js under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.I18N_SCRIPT_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.I18N_SCRIPT_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_gantt_i18n_script_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, "i18n_apply")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.gantt_script_source("i18n_apply")
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": GanttScriptGenerationProcessState.I18N_SCRIPT_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
