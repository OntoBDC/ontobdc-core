import pytest

from ontobdc.view.adapter.surface.document import (
    assemble_surface_markup,
    embed_component_scripts,
    set_state_marker,
    upsert_json_script,
)


MALFORMED_DOCUMENT = "<!doctype html><html><p>no head or body closing tags</p></html>"


def test_set_state_marker_raises_on_missing_head_close() -> None:
    with pytest.raises(ValueError, match="missing a closing <head>"):
        set_state_marker(MALFORMED_DOCUMENT, "surface_initialized")


def test_upsert_json_script_raises_on_missing_head_close() -> None:
    with pytest.raises(ValueError, match="missing a closing <head>"):
        upsert_json_script(MALFORMED_DOCUMENT, "ontobdc-surface-jsonld", {"a": 1})


def test_assemble_surface_markup_raises_on_missing_body_close() -> None:
    with pytest.raises(ValueError, match="missing a closing <body>"):
        assemble_surface_markup(MALFORMED_DOCUMENT, [])


def test_embed_component_scripts_raises_on_missing_body_close() -> None:
    with pytest.raises(ValueError, match="missing a closing <body>"):
        embed_component_scripts(MALFORMED_DOCUMENT, ["console.log('x')"])


def test_embed_component_scripts_is_a_noop_without_scripts() -> None:
    assert embed_component_scripts(MALFORMED_DOCUMENT, []) == MALFORMED_DOCUMENT
