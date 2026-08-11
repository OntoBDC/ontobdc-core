import json
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import JSONLD_ID, set_state_marker, upsert_json_script
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.capability.transformation.data_gathered import DataGatheredCapability
from ontobdc.view.plugin.check.is_surface_enriched.check import main as check_surface_enriched


class SurfaceEnrichedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_enriched",
        version="1.0.0",
        name="Surface Enriched",
        description="Embed Surface semantic data and metadata as JSON-LD.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "json-ld", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ENRICHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ENRICHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_enriched)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        payload = self._gathered_jsonld(context)
        document = self._surface.read(context)
        document = upsert_json_script(document, JSONLD_ID, payload, "application/ld+json")
        document = set_state_marker(document, "surface_enriched")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_enriched, "surface_enriched")

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_ENRICHED,
            "surface_path": str(path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _gathered_jsonld(self, context: CliContextPort) -> Any:
        """Read the JSON-LD DATA_GATHERED wrote, rather than a context hand-off.

        A context parameter would only be populated if DATA_GATHERED's
        `execute()` ran in this same process invocation; the state artifact
        on disk is the one thing guaranteed to exist whenever `check()`
        reports the state as satisfied, including when it was satisfied by
        a previous run.
        """
        path = DataGatheredCapability.state_path(context)
        return json.loads(path.read_text(encoding="utf-8"))
