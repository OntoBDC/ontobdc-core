import io

from ontobdc.view.component.logo.python import LogoComponent


def test_logo_component_renders_terminal_logo_with_version() -> None:
    component = LogoComponent(version="0.14.0", center=False, color=False)

    rendered = component.render()

    assert "OntoBDC" not in rendered
    assert "v0.14.0" in rendered
    assert "_" in rendered or "|" in rendered


def test_logo_component_can_print_to_stream() -> None:
    stream = io.StringIO()
    component = LogoComponent(version="1.2.3", center=False, color=False)

    component.print(file=stream)

    assert "v1.2.3" in stream.getvalue()


def test_logo_component_exposes_brand_rgb() -> None:
    assert LogoComponent(color=False).rgb() == (25, 70, 109)


def test_logo_component_colors_onto_white_and_bdc_brand_color() -> None:
    component = LogoComponent(center=False, color=True)

    rendered = component.render()

    white_code = "\x1b[38;2;255;255;255m"
    accent_code = "\x1b[1;38;2;25;70;109m"
    assert white_code in rendered
    assert accent_code in rendered
    # "Onto" must be colored white before "BDC" turns to the bold brand
    # color on every glyph row of the banner.
    for line in rendered.splitlines():
        if not line.strip():
            continue
        assert line.index(white_code) < line.index(accent_code)


def test_logo_component_renders_bdc_in_bold() -> None:
    component = LogoComponent(center=False, color=True)

    rendered = component.render()

    assert "\x1b[1;38;2;25;70;109m" in rendered


def test_render_compact_is_a_single_line_marker_plus_name_without_color() -> None:
    component = LogoComponent(color=False)

    assert component.render_compact() == ">_ OntoBDC"


def test_render_compact_colors_onto_white_and_bdc_brand_color() -> None:
    component = LogoComponent(color=True)

    rendered = component.render_compact()

    white_code = "\x1b[38;2;255;255;255m"
    accent_code = "\x1b[1;38;2;25;70;109m"
    assert rendered.startswith(">_ ")
    assert white_code in rendered
    assert accent_code in rendered
    assert rendered.index(white_code) < rendered.index(accent_code)
