import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import JSONLD_ID, extract_json_script, set_state_marker
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_entity_views_published.check import (
    main as check_entity_views_published,
)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


class EntityViewsPublishedCapability(TransformationCapability):
    """Publish a standalone detail page for every entity `ontobdc_view` has
    a Page renderer for.

    Thin orchestration only: this capability enumerates entities from the
    already-resolved Surface JSON-LD and delegates rendering (and the
    decision of whether an entity type has a page at all) entirely to
    `ontobdc_view.render_entity_view`. It has no per-entity-type knowledge,
    no HTML/Jinja logic, and no separate staleness check — every run
    regenerates every matched page fresh, the same way `index.html` itself
    has no incremental repair step, just full regeneration.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.entity_views_published",
        version="1.0.0",
        name="Entity Views Published",
        description=(
            "Publish a standalone detail page for every entity ontobdc_view "
            "has a Page renderer for."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "html", "page", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_entity_views_published)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import ontobdc_view
        except ImportError:
            document = self._surface.read(context)
            document = set_state_marker(document, "entity_views_published")
            self._surface.write(context, document)
            return {
                "resulting_state": SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED,
                "published_view_count": 0,
            }

        document = self._surface.read(context)
        container_path = self._surface.path(context).parent
        nodes = self._entity_nodes(document)

        published: List[str] = []
        for node in nodes:
            result = ontobdc_view.render_entity_view(
                self._type_uris(node), node, graph_nodes=nodes
            )
            if result is None:
                continue
            identifier = str(result.get("identifier") or "").strip()
            path_segment = str(result.get("path_segment") or "").strip()
            html = result.get("html")
            if not identifier or not path_segment or not isinstance(html, str):
                continue
            target_path = (
                container_path / ".__ontobdc__" / "view" / path_segment / f"{identifier}.html"
            )
            _atomic_write_text(target_path, html)
            published.append(str(target_path))

        document = set_state_marker(document, "entity_views_published")
        self._surface.write(context, document)

        return {
            "resulting_state": SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED,
            "published_view_count": len(published),
            "published_view_paths": published,
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _entity_nodes(self, document: str) -> List[Dict[str, Any]]:
        try:
            graph = extract_json_script(document, JSONLD_ID)
        except (ValueError, json.JSONDecodeError):
            return []
        if isinstance(graph, dict):
            return [graph]
        if isinstance(graph, list):
            return [node for node in graph if isinstance(node, dict)]
        return []

    def _type_uris(self, node: Dict[str, Any]) -> List[str]:
        raw_type = node.get("@type")
        if isinstance(raw_type, str):
            return [raw_type]
        if isinstance(raw_type, list):
            return [str(item) for item in raw_type]
        return []
