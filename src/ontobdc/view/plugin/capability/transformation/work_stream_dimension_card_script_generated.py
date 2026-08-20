from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.work_stream_script_state import (
    WorkStreamScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.work_stream_script_common import script_path
from ontobdc.view.plugin.check.is_work_stream_dimension_card_script_generated.check import (
    main as check_work_stream_dimension_card_script_generated,
)


class WorkStreamDimensionCardScriptGeneratedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.work_stream_dimension_card_script_generated",
        version="1.0.0",
        name="WorkStream Dimension Card Script Generated",
        description="dimension_card.js builds each 5W2H dimension card's DOM and wires the page's render() bootstrap.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "workstream", "script", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "dimension_card.js was generated under .__ontobdc__/asset/work_stream_view/.",
            },
            "debug_entry": {
                "en": "Generating dimension_card.js under .__ontobdc__/asset/work_stream_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return WorkStreamScriptGenerationProcessState.DIMENSION_CARD_SCRIPT_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return WorkStreamScriptGenerationProcessState.DIMENSION_CARD_SCRIPT_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_work_stream_dimension_card_script_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, "dimension_card")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.work_stream_script_source("dimension_card")
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": WorkStreamScriptGenerationProcessState.DIMENSION_CARD_SCRIPT_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
