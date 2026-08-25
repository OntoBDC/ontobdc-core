import re
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import (
    LANGUAGE_PARAM,
    THEME_PARAM,
    embed_url_state_bootstrap,
    set_state_marker,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.surface_common import state_reached


_HTML_LANG_RE = re.compile(r"<html\b[^>]*\blang=[\"']([^\"']+)[\"']", re.IGNORECASE)


class SurfaceParametersEnsuredCapability(TransformationCapability):
    """Declare the default value of every URL-controlled presentation parameter.

    The address bar is the only store for language and theme — no cookie, no
    localStorage, no second in-page state — which leaves one gap: the very
    first open of a generated page carries no parameters at all, so what it
    renders depends on build-time knowledge that the URL does not express and
    a reload cannot reproduce.

    This step closes it by embedding the runtime that owns URL presentation
    state (`embed_url_state_bootstrap`) together with the defaults resolved
    here. At runtime that bootstrap normalizes the address bar, applies the
    URL language before first paint, and exposes the single helper every
    Tile uses to carry the live state onto an internal link — so no component
    parses or rewrites the query string on its own.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "surface_parameters_ensured"
        ),
        version="1.0.0",
        name="Surface Parameters Ensured",
        description=(
            "Embed the default value of every URL-controlled presentation "
            "parameter, and the runtime that normalizes them into the address "
            "bar and propagates them across internal links."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "url", "language", "theme", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Default URL presentation parameters were declared, and the "
                    "Surface can normalize its own address bar and propagate the "
                    "active state across internal links."
                ),
            },
            "debug_entry": {
                "en": (
                    "Declaring default URL presentation parameters and embedding "
                    "the URL state runtime."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PARAMETERS_ENSURED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PARAMETERS_ENSURED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        try:
            document = self._surface.read(context)
        except (OSError, ValueError):
            return False
        return state_reached(
            document,
            SurfaceGenerationProcessState.SURFACE_PARAMETERS_ENSURED,
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        defaults = self.resolve_defaults(context, document)
        document = embed_url_state_bootstrap(document, defaults)
        document = set_state_marker(document, "surface_parameters_ensured")
        surface_path = self._surface.write(context, document)
        if not self.check(context):
            raise RuntimeError(
                "Surface parameter transformation did not reach "
                "surface_parameters_ensured"
            )
        return {
            "resulting_state": (
                SurfaceGenerationProcessState.SURFACE_PARAMETERS_ENSURED
            ),
            "surface_path": str(surface_path),
            "url_state_defaults": defaults,
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    @classmethod
    def resolve_defaults(
        cls,
        context: CliContextPort,
        document: str,
    ) -> Dict[str, str]:
        """The value each canonical parameter falls back to when the URL omits it.

        Language comes from the generation request, and falls back to the
        `<html lang>` the document was initialized with so the default can
        never contradict the markup. Theme comes from `ontobdc_view`'s own
        catalog — the same list `onto-theme-tile` cycles through, whose first
        entry is what the tile already selects when nothing is requested — and
        is simply omitted when `ontobdc_view` is unavailable, exactly as the
        other optional `ontobdc_view` touchpoints in this pipeline behave.
        """
        defaults: Dict[str, str] = {LANGUAGE_PARAM: cls._default_language(context, document)}
        theme = cls._default_theme()
        if theme:
            defaults[THEME_PARAM] = theme
        return defaults

    @staticmethod
    def _default_language(context: CliContextPort, document: str) -> str:
        requested = str(context.get_parameter_value("language") or "").strip()
        if requested:
            return requested
        match = _HTML_LANG_RE.search(document)
        if match:
            return match.group(1).strip() or "en"
        return "en"

    @staticmethod
    def _default_theme() -> str:
        try:
            import ontobdc_view

            catalog = ontobdc_view.theme_catalog()
        except Exception:
            return ""
        if not isinstance(catalog, list) or not catalog:
            return ""
        first = catalog[0]
        if not isinstance(first, dict):
            return ""
        return str(first.get("name") or "").strip()
