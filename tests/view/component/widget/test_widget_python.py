from ontobdc.view.component.widget.python import (
    CodeBlockWidget,
    ErrorWidget,
    GridWidget,
    KeyValueWidget,
    TableWidget,
    TextWidget,
)


def test_text_widget_renders_heading_then_wrapped_body() -> None:
    widget = TextWidget(heading="Title", body="one two three four five")

    lines = widget.render(available_columns=11)

    assert lines[0] == "Title"
    assert lines[1] == ""
    assert all(len(line) <= 11 for line in lines[2:])
    assert " ".join(lines[2:]) == "one two three four five"


def test_text_widget_renders_headings_and_bullets_from_markdown_lite_body() -> None:
    widget = TextWidget(body="# Heading\n\nintro\n\n- first\n- second")

    lines = widget.render(available_columns=40)

    assert "Heading" in lines
    assert "intro" in lines
    assert "• first" in lines
    assert "• second" in lines


def test_text_widget_strips_bold_and_inline_code_markers() -> None:
    widget = TextWidget(body="this is **bold** and `code`")

    lines = widget.render(available_columns=80)

    assert lines == ["this is bold and code"]


def test_text_widget_with_nothing_set_renders_no_lines() -> None:
    assert TextWidget().render(available_columns=80) == []


def test_key_value_widget_aligns_and_wraps_long_values() -> None:
    widget = KeyValueWidget(pairs=[("name", "OntoBDC"), ("summary", "a rather long value that wraps")])

    lines = widget.render(available_columns=24)

    assert lines[0].startswith("name")
    assert all(len(line) <= 24 for line in lines)


def test_key_value_widget_with_no_pairs_renders_no_lines() -> None:
    assert KeyValueWidget().render(available_columns=80) == []


def test_table_widget_aligns_columns_and_pads_missing_cells() -> None:
    widget = TableWidget(headers=["name", "size"], rows=[["a", "1"], ["bb", "22"]])

    lines = widget.render(available_columns=80)

    assert lines[0].startswith("name")
    assert lines[1].startswith("a ")
    assert lines[2].startswith("bb")


def test_table_widget_shrinks_columns_to_fit_available_width() -> None:
    widget = TableWidget(
        headers=["name", "description"],
        rows=[["a", "a very long description that would not otherwise fit"]],
    )

    lines = widget.render(available_columns=30)

    assert all(len(line) <= 30 for line in lines)


def test_table_widget_with_no_headers_renders_no_lines() -> None:
    assert TableWidget().render(available_columns=80) == []


def test_code_block_widget_renders_verbatim_without_reflow() -> None:
    widget = CodeBlockWidget(text='{\n  "a": 1\n}')

    lines = widget.render(available_columns=5)

    assert lines == ["{", '  "a": 1', "}"]


def test_error_widget_without_traceback() -> None:
    widget = ErrorWidget(message="boom")

    assert widget.render(available_columns=80) == ["Error: boom"]


def test_error_widget_with_traceback() -> None:
    widget = ErrorWidget(message="boom", traceback="line 1\nline 2")

    lines = widget.render(available_columns=80)

    assert lines == ["Error: boom", "", "Traceback:", "line 1", "line 2"]


def test_grid_widget_draws_bordered_cells_labeled_with_coordinates() -> None:
    widget = GridWidget(columns=2, rows=2, slot_width=6, slot_height=1)

    lines = widget.render(available_columns=80)

    assert lines[0] == "+------+------+"
    assert lines == [
        "+------+------+",
        f"|{'0,0'.center(6)}|{'0,1'.center(6)}|",
        "+------+------+",
        f"|{'1,0'.center(6)}|{'1,1'.center(6)}|",
        "+------+------+",
    ]


def test_grid_widget_shows_coordinate_and_size_on_two_lines_within_a_taller_slot() -> None:
    widget = GridWidget(columns=1, rows=1, slot_width=4, slot_height=3)

    lines = widget.render(available_columns=80)

    assert lines == [
        "+----+",
        f"|{'0,0'.center(4)}|",
        f"|{'4x3'.center(4)}|",
        "|    |",
        "+----+",
    ]


def test_grid_widget_with_default_single_cell() -> None:
    assert GridWidget().render(available_columns=80)[0] == "+" + "-" * 20 + "+"


def test_grid_widget_draws_an_operation_band_above_the_tile_grid() -> None:
    widget = GridWidget(columns=2, rows=1, slot_width=6, slot_height=1, operation_enabled=True)

    lines = widget.render(available_columns=80)

    assert lines == [
        "+-------------+",
        f"|{'operation'.center(13)}|",
        "+-------------+",
        "+------+------+",
        f"|{'0,0'.center(6)}|{'0,1'.center(6)}|",
        "+------+------+",
    ]


def test_grid_widget_draws_a_pinned_band_below_the_tile_grid() -> None:
    widget = GridWidget(columns=2, rows=1, slot_width=6, slot_height=1, pinned_enabled=True)

    lines = widget.render(available_columns=80)

    assert lines == [
        "+------+------+",
        f"|{'0,0'.center(6)}|{'0,1'.center(6)}|",
        "+------+------+",
        "+-------------+",
        f"|{'pinned'.center(13)}|",
        "+-------------+",
    ]


def test_grid_widget_draws_neither_band_by_default() -> None:
    widget = GridWidget(columns=1, rows=1, slot_width=4, slot_height=1)

    lines = widget.render(available_columns=80)

    assert "operation" not in "\n".join(lines)
    assert "pinned" not in "\n".join(lines)
    assert len(lines) == 3
