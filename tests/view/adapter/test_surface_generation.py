from pathlib import Path
from typing import Any, Dict

import pytest

from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.capability.surface_assembled import SurfaceAssembledCapability
from ontobdc.view.plugin.capability.surface_enriched import SurfaceEnrichedCapability
from ontobdc.view.plugin.capability.surface_initialized import SurfaceInitializedCapability
from ontobdc.view.plugin.capability.surface_matched import SurfaceMatchedCapability
from ontobdc.view.plugin.capability.surface_packaged import SurfacePackagedCapability
from ontobdc.view.plugin.capability.surface_set import SurfaceSetCapability
from ontobdc.view.plugin.capability.surface_validated import SurfaceValidatedCapability
from ontobdc.view.plugin.check.is_surface_assembled.check import main as check_surface_assembled
from ontobdc.view.plugin.check.is_surface_enriched.check import main as check_surface_enriched
from ontobdc.view.plugin.check.is_surface_initialized.check import main as check_surface_initialized
from ontobdc.view.plugin.check.is_surface_matched.check import main as check_surface_matched
from ontobdc.view.plugin.check.is_surface_packaged.check import main as check_surface_packaged
from ontobdc.view.plugin.check.is_surface_set.check import main as check_surface_set
from ontobdc.view.plugin.check.is_surface_validated.check import main as check_surface_validated


class FakeContext:
    def __init__(self, root_path: Path, **parameters: Any) -> None:
        self._root_path = root_path
        self._parameters: Dict[str, Any] = dict(parameters)

    @property
    def root_path(self) -> str:
        return str(self._root_path)

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def has_parameter(self, name: str) -> bool:
        return name in self._parameters


def _context(tmp_path: Path) -> FakeContext:
    return FakeContext(
        tmp_path,
        surface_path=str(tmp_path / "surface.html"),
        language="pt-br",
        surface_jsonld={
            "@context": {"schema": "https://schema.org/"},
            "@graph": [
                {
                    "@id": "urn:photo:1",
                    "@type": "schema:ImageObject",
                    "schema:name": "Photo 1",
                }
            ],
        },
        surface_config={
            "operation": {"enabled": True},
            "content": {"mode": "scroll"},
            "pinned": {"enabled": True},
            "slotTarget": 72,
            "gap": 12,
            "padding": 16,
            "tileMargin": 6,
        },
        surface_matches=[
            {
                "tile": "onto-theme-tile",
                "region": "operation",
                "minColumns": 1,
                "preferredColumns": 1,
                "maxColumns": 1,
                "minRows": 1,
                "preferredRows": 1,
                "maxRows": 1,
            },
            {
                "tile": "onto-photo-tile",
                "data": "urn:photo:1",
                "region": "content",
                "minColumns": 1,
                "preferredColumns": 2,
                "maxColumns": 4,
                "minRows": 1,
                "preferredRows": 2,
                "maxRows": 3,
            },
        ],
        surface_component_scripts=[
            "customElements.get('onto-presentation-surface') || customElements.define('onto-presentation-surface', class extends HTMLElement {});",
            "customElements.get('onto-theme-tile') || customElements.define('onto-theme-tile', class extends HTMLElement {});",
            "customElements.get('onto-photo-tile') || customElements.define('onto-photo-tile', class extends HTMLElement {});",
        ],
    )


def test_surface_transformations_build_cumulative_offline_html(tmp_path: Path) -> None:
    context = _context(tmp_path)
    surface_path = Path(context.get_parameter_value("surface_path"))

    initialized = SurfaceInitializedCapability().execute(context)
    assert initialized["resulting_state"] == SurfaceGenerationProcessState.SURFACE_INITIALIZED
    assert check_surface_initialized(str(surface_path)) == 0
    assert check_surface_enriched(str(surface_path)) != 0

    SurfaceEnrichedCapability().execute(context)
    assert check_surface_enriched(str(surface_path)) == 0
    assert check_surface_set(str(surface_path)) != 0

    SurfaceSetCapability().execute(context)
    assert check_surface_set(str(surface_path)) == 0
    assert check_surface_matched(str(surface_path)) != 0

    SurfaceMatchedCapability().execute(context)
    assert check_surface_matched(str(surface_path)) == 0
    assert check_surface_assembled(str(surface_path)) != 0

    SurfaceAssembledCapability().execute(context)
    assert check_surface_assembled(str(surface_path)) == 0
    assert check_surface_packaged(str(surface_path)) != 0

    SurfacePackagedCapability().execute(context)
    assert check_surface_packaged(str(surface_path)) == 0
    assert check_surface_validated(str(surface_path)) != 0

    SurfaceValidatedCapability().execute(context)
    assert check_surface_validated(str(surface_path)) == 0

    document = surface_path.read_text(encoding="utf-8")
    assert 'type="application/ld+json" id="ontobdc-surface-jsonld"' in document
    assert 'id="ontobdc-surface-config"' in document
    assert 'id="ontobdc-surface-matches"' in document
    assert 'surface-region="operation"' in document
    assert 'surface-region="content"' in document
    assert 'data-ontobdc-assembled="true"' in document
    assert "data-ontobdc-surface-component" in document
    assert "https://cdn." not in document


def test_content_match_requires_a_data_binding(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.set_parameter_value(
        "surface_matches",
        [
            {
                "tile": "onto-photo-tile",
                "region": "content",
                "minColumns": 1,
                "preferredColumns": 1,
                "maxColumns": 2,
                "minRows": 1,
                "preferredRows": 1,
                "maxRows": 2,
            }
        ],
    )

    SurfaceInitializedCapability().execute(context)
    SurfaceEnrichedCapability().execute(context)
    SurfaceSetCapability().execute(context)

    with pytest.raises(ValueError, match="data is required for content Tiles"):
        SurfaceMatchedCapability().execute(context)
