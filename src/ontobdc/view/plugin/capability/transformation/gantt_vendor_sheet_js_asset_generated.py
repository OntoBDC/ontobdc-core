from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.gantt_script_state import (
    GanttScriptGenerationProcessState,
)
from ontobdc.view.plugin.check.gantt_script_common import script_path
from ontobdc.view.plugin.check.is_gantt_vendor_sheet_js_asset_generated.check import (
    VENDOR_SHEET_JS_NAME,
    main as check_vendor_sheet_js_asset_generated,
)


class GanttVendorSheetJsAssetGeneratedCapability(TransformationCapability):
    """Materialize the vendored SheetJS build the Gantt Page loads.

    The Page lists this file among its script tags exactly like the generated
    ones, so it is written by a state of the same machine rather than by a
    copy step alongside it. A library the Page names but no state produces
    goes missing with nothing failing at build time.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.gantt_vendor_sheet_js_asset_generated",
        version="1.0.0",
        name="Gantt Vendored SheetJS Asset Generated",
        description=(
            "xlsx-0.18.5.full.min.js is the vendored SheetJS build the Gantt "
            "Page loads before its own runtime, used to read workbooks in the "
            "browser."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "ifc-workschedule", "vendor", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "xlsx-0.18.5.full.min.js was written under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
            "debug_entry": {
                "en": "Writing xlsx-0.18.5.full.min.js under .__ontobdc__/asset/ifc_work_schedule_view/.",
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.VENDOR_SHEET_JS_ASSET_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GanttScriptGenerationProcessState.VENDOR_SHEET_JS_ASSET_GENERATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return (
            check_vendor_sheet_js_asset_generated(
                surface_path=str(self._surface.path(context))
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ontobdc_view

        container_path = self._surface.path(context).parent
        target_path = script_path(container_path, VENDOR_SHEET_JS_NAME)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        content = ontobdc_view.gantt_script_source(VENDOR_SHEET_JS_NAME)
        target_path.write_text(content, encoding="utf-8")
        return {
            "resulting_state": GanttScriptGenerationProcessState.VENDOR_SHEET_JS_ASSET_GENERATED,
            "script_path": str(target_path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
