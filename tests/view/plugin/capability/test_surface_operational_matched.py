import json
from pathlib import Path
from typing import Any, Dict

import pytest

from ontobdc.view.adapter.surface.document import DEFAULT_LAYOUTS_ID, MATCHES_ID, extract_json_script
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.capability.transformation.data_gathered import DataGatheredCapability
from ontobdc.view.plugin.capability.transformation.surface_assembled import SurfaceAssembledCapability
from ontobdc.view.plugin.capability.transformation.surface_enriched import SurfaceEnrichedCapability
from ontobdc.view.plugin.capability.transformation.surface_initialized import SurfaceInitializedCapability
from ontobdc.view.plugin.capability.transformation.surface_matched import SurfaceMatchedCapability
from ontobdc.view.plugin.capability.transformation.surface_operational_matched import (
    SurfaceOperationalMatchedCapability,
)
from ontobdc.view.plugin.capability.transformation.surface_set import SurfaceSetCapability
from ontobdc.view.plugin.check.is_surface_assembled.check import main as check_surface_assembled
from ontobdc.view.plugin.check.is_surface_operational_matched.check import (
    main as check_surface_operational_matched,
)

VIEW = "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#"

WIDE_LAYOUT_WITH_LOGO_TURTLE = f"""
@prefix view: <{VIEW}> .
@prefix layout: <urn:ontobdc:layout:> .

layout:wide
    a view:DefaultSurfaceLayout ;
    view:minAvailableColumns 9 ;
    view:layoutPriority 10 ;
    view:columnCount 12 ;
    view:rowCount 12 ;
    view:hasRegion layout:operation .

layout:operation
    a view:OperationRegion ;
    view:rowStart 1 ; view:columnStart 1 ; view:rowSpan 1 ; view:columnSpan 12 ;
    view:scrollable false ;
    view:hasComponentPlacement layout:logoPlacement .

layout:logo a view:LogoTile .

layout:logoPlacement
    a view:ComponentPlacement ;
    view:placesComponent layout:logo ;
    view:hasAlignment view:StartAlignment ;
    view:placementOrder 10 .
"""

UNRESOLVABLE_PLACEMENT_TURTLE = f"""
@prefix view: <{VIEW}> .
@prefix layout: <urn:ontobdc:layout:> .

layout:wide
    a view:DefaultSurfaceLayout ;
    view:hasRegion layout:operation .

layout:operation
    a view:OperationRegion ;
    view:hasComponentPlacement layout:placement .

layout:mystery a view:Tile .

layout:placement
    a view:ComponentPlacement ;
    view:placesComponent layout:mystery ;
    view:placementOrder 10 .
"""


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


def _context_at_surface_matched(tmp_path: Path, **extra_parameters: Any) -> FakeContext:
    context = FakeContext(
        tmp_path,
        surface_path=str(tmp_path / "surface.html"),
        language="pt-br",
        container_path=str(tmp_path),
        surface_config={
            "operation": {"enabled": True},
            "content": {"mode": "scroll"},
            "pinned": {"enabled": True},
            "slotTarget": 72,
            "gap": 12,
            "padding": 16,
            "tileMargin": 6,
        },
        **extra_parameters,
    )
    # `SurfaceEnrichedCapability` reads the DATA_GATHERED artifact from disk
    # (`DataGatheredCapability.state_path`), not from a context parameter —
    # writing it directly here is far cheaper than building a real container
    # for `DataGatheredCapability.execute()` to run against.
    state_path = DataGatheredCapability.state_path(context)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"@context": {"schema": "https://schema.org/"}, "@graph": []}),
        encoding="utf-8",
    )

    SurfaceInitializedCapability().execute(context)
    SurfaceEnrichedCapability().execute(context)
    SurfaceSetCapability().execute(context)
    SurfaceMatchedCapability().execute(context)
    return context


def _matches(surface_path: Path):
    return extract_json_script(surface_path.read_text(encoding="utf-8"), MATCHES_ID)


def test_no_layouts_configured_falls_back_to_the_shipped_default(tmp_path: Path) -> None:
    # A container that configures no view.surfaceLayoutsPath still gets a
    # sensible operational Surface — ontobdc_view.default_surface_layouts()
    # (Logo/Language/Theme) applies instead of leaving OperationRegion empty.
    context = _context_at_surface_matched(tmp_path, surface_matches=[])
    surface_path = Path(context.get_parameter_value("surface_path"))

    result = SurfaceOperationalMatchedCapability().execute(context)

    assert result["resulting_state"] == SurfaceGenerationProcessState.SURFACE_OPERATIONAL_MATCHED
    assert result["default_layout_count"] == 1
    matches = _matches(surface_path)
    injected_tags = {m["tile"] for m in matches}
    assert {"onto-logo-tile", "onto-language-tile", "onto-theme-tile"}.issubset(injected_tags)

    document = surface_path.read_text(encoding="utf-8")
    assert DEFAULT_LAYOUTS_ID in document
    assert check_surface_operational_matched(str(surface_path)) == 0


def test_operation_region_placement_is_injected_as_a_match(tmp_path: Path) -> None:
    layouts_path = tmp_path / "layouts.ttl"
    layouts_path.write_text(WIDE_LAYOUT_WITH_LOGO_TURTLE, encoding="utf-8")
    context = _context_at_surface_matched(
        tmp_path, surface_matches=[], surface_layouts_path=str(layouts_path)
    )
    surface_path = Path(context.get_parameter_value("surface_path"))

    result = SurfaceOperationalMatchedCapability().execute(context)

    assert result["operational_match_count"] == 1
    assert result["default_layout_count"] == 1
    matches = _matches(surface_path)
    injected = next(m for m in matches if m["tile"] == "onto-logo-tile")
    assert injected["region"] == "operation"
    assert injected["minRows"] == 1 and injected["maxRows"] == 1

    document = surface_path.read_text(encoding="utf-8")
    layouts_payload = extract_json_script(document, DEFAULT_LAYOUTS_ID)
    assert layouts_payload[0]["iri"] == "urn:ontobdc:layout:wide"
    assert "ontobdc-surface-default-layouts-bootstrap" in document
    assert check_surface_operational_matched(str(surface_path)) == 0


def test_explicit_match_is_not_duplicated(tmp_path: Path) -> None:
    layouts_path = tmp_path / "layouts.ttl"
    layouts_path.write_text(WIDE_LAYOUT_WITH_LOGO_TURTLE, encoding="utf-8")
    context = _context_at_surface_matched(
        tmp_path,
        surface_layouts_path=str(layouts_path),
        surface_matches=[
            {
                "tile": "onto-logo-tile",
                "tileClass": f"{VIEW}LogoTile",
                "region": "operation",
                "minColumns": 2,
                "preferredColumns": 2,
                "maxColumns": 2,
                "minRows": 1,
                "preferredRows": 1,
                "maxRows": 1,
            }
        ],
    )
    surface_path = Path(context.get_parameter_value("surface_path"))

    result = SurfaceOperationalMatchedCapability().execute(context)

    assert result["operational_match_count"] == 0
    logo_matches = [m for m in _matches(surface_path) if m["tile"] == "onto-logo-tile"]
    assert len(logo_matches) == 1
    assert logo_matches[0]["preferredColumns"] == 2  # the caller's explicit envelope, untouched


def test_unresolvable_placement_raises(tmp_path: Path) -> None:
    layouts_path = tmp_path / "layouts.ttl"
    layouts_path.write_text(UNRESOLVABLE_PLACEMENT_TURTLE, encoding="utf-8")
    context = _context_at_surface_matched(
        tmp_path, surface_matches=[], surface_layouts_path=str(layouts_path)
    )

    with pytest.raises(ValueError, match="No registered Component implements"):
        SurfaceOperationalMatchedCapability().execute(context)


def test_surface_assembled_still_passes_after_the_new_state(tmp_path: Path) -> None:
    layouts_path = tmp_path / "layouts.ttl"
    layouts_path.write_text(WIDE_LAYOUT_WITH_LOGO_TURTLE, encoding="utf-8")
    context = _context_at_surface_matched(
        tmp_path, surface_matches=[], surface_layouts_path=str(layouts_path)
    )
    surface_path = Path(context.get_parameter_value("surface_path"))

    SurfaceOperationalMatchedCapability().execute(context)
    assert check_surface_operational_matched(str(surface_path)) == 0
    assert check_surface_assembled(str(surface_path)) != 0

    SurfaceAssembledCapability().execute(context)
    assert check_surface_assembled(str(surface_path)) == 0

    document = surface_path.read_text(encoding="utf-8")
    assert '<onto-logo-tile' in document
    assert 'surface-region="operation"' in document
