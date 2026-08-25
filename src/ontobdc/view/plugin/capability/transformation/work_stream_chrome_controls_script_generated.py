from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.work_stream_script_state import (
    WorkStreamScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.work_stream_script_common import script_path
from ontobdc.view.plugin.check.is_work_stream_chrome_controls_script_generated.check import (
    main as check_work_stream_chrome_controls_script_generated,
)


class WorkStreamChromeControlsScriptGeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.work_stream_chrome_controls_script_generated",
        version="1.0.0",
        name="WorkStream Chrome Controls Script Generated",
        description="chrome_controls.js wires the header chrome (connect-btn click listener, status indicator, refresh/workspace/subjects buttons) shared between WorkStream and Gantt pages, including the wireAnnotationControls alias for dimension_card backward compatibility.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "workstream", "script", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "chrome_controls.js was generated under .__ontobdc__/asset/work_stream_view/.",
            },
            "debug_entry": {
                "en": "Generating chrome_controls.js under .__ontobdc__/asset/work_stream_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return WorkStreamScriptGenerationProcessState.CHROME_CONTROLS_SCRIPT_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return WorkStreamScriptGenerationProcessState.CHROME_CONTROLS_SCRIPT_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_work_stream_chrome_controls_script_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, "chrome_controls")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.work_stream_script_source("chrome_controls")
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": WorkStreamScriptGenerationProcessState.CHROME_CONTROLS_SCRIPT_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
