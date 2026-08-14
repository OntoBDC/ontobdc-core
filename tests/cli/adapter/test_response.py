from ontobdc.cli.adapter.response import (
    CommandResponseWidgetAdapter,
    ExceptionCommandResponseWidgetAdapter,
    GridCommandResponseWidgetAdapter,
    HelpCommandResponseWidgetAdapter,
    ListCommandResponseWidgetAdapter,
    WelcomeCommandResponseWidgetAdapter,
)
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    GridCommandResponse,
    HelpCommandResponse,
    ListCommandResponse,
    WelcomeCommandResponse,
)
from ontobdc.view.component.widget.python import (
    CodeBlockWidget,
    ErrorWidget,
    GridWidget,
    KeyValueWidget,
    TableWidget,
    TextWidget,
)


def test_command_response_widgets_lead_with_a_heading() -> None:
    adapter = CommandResponseWidgetAdapter()
    response = CommandResponse(title="T", description="D")

    widgets = adapter.widgets(response)

    assert isinstance(widgets[0], TextWidget)
    assert widgets[0].heading == "T"
    assert widgets[0].body == "D"


def test_command_response_with_flat_content_becomes_key_value_widget() -> None:
    adapter = CommandResponseWidgetAdapter()
    response = CommandResponse(title="T", description="D", content={"branch": "main", "ahead": 3})

    widgets = adapter.widgets(response)

    assert len(widgets) == 2
    assert isinstance(widgets[1], KeyValueWidget)
    assert widgets[1].pairs == [("branch", "main"), ("ahead", "3")]


def test_command_response_with_a_single_nested_record_becomes_a_labeled_section() -> None:
    adapter = CommandResponseWidgetAdapter()
    response = CommandResponse(title="T", description="D", content={"a": {"b": 1}})

    widgets = adapter.widgets(response)

    assert isinstance(widgets[1], TextWidget)
    assert widgets[1].heading == "a"
    assert isinstance(widgets[2], KeyValueWidget)
    assert widgets[2].pairs == [("b", "1")]


def test_help_shaped_content_sections_a_scalar_list_and_a_dict_of_records_into_a_table() -> None:
    # This is the actual shape CliBaseCommand.run() builds for `ontobdc --help`
    # (cli/plugin/command/base.py): {"Usage": [...], "Commands": {flag: {...}}}.
    adapter = HelpCommandResponseWidgetAdapter()
    response = HelpCommandResponse(
        title="CLI Help",
        description="Display help information for the CLI.",
        content={
            "Usage": ["ontobdc <command> [flags/parameters]"],
            "Commands": {
                "--version": {"id": "version", "accepts": ["--version"], "description": "Show version"},
                "--init": {"id": "init", "accepts": ["--init"], "description": "Initialize a project"},
            },
        },
    )

    widgets = adapter.widgets(response)

    assert isinstance(widgets[1], TextWidget) and widgets[1].heading == "Usage"
    assert isinstance(widgets[2], TextWidget)
    assert widgets[2].body == "- ontobdc <command> [flags/parameters]"

    assert isinstance(widgets[3], TextWidget) and widgets[3].heading == "Commands"
    table = widgets[4]
    assert isinstance(table, TableWidget)
    assert table.headers == ["Key", "id", "accepts", "description"]
    assert table.rows == [
        ["--version", "version", "--version", "Show version"],
        ["--init", "init", "--init", "Initialize a project"],
    ]


def test_content_that_still_does_not_fit_any_widget_falls_back_to_code_block() -> None:
    adapter = CommandResponseWidgetAdapter()
    response = CommandResponse(title="T", description="D", content={"mixed": [1, {"x": 1}]})

    widgets = adapter.widgets(response)

    assert widgets[1].heading == "mixed"
    assert isinstance(widgets[2], CodeBlockWidget)
    assert '"x"' in widgets[2].text


def test_help_response_accepts_help_command_response() -> None:
    adapter = HelpCommandResponseWidgetAdapter()
    assert adapter.accepts(HelpCommandResponse(title="T", description="D"))
    assert not adapter.accepts(CommandResponse(title="T", description="D"))


def test_list_response_with_rows_becomes_key_value_widget() -> None:
    adapter = ListCommandResponseWidgetAdapter()
    response = ListCommandResponse(
        title="Items",
        description="Some items",
        content={"rows": [{"label": "Name", "value": "OntoBDC"}]},
    )

    widgets = adapter.widgets(response)

    assert isinstance(widgets[1], KeyValueWidget)
    assert widgets[1].pairs == [("Name", "OntoBDC")]


def test_list_response_with_harmonious_items_becomes_table_widget() -> None:
    adapter = ListCommandResponseWidgetAdapter()
    response = ListCommandResponse(
        title="Items",
        description="Some items",
        content=[{"name": "a", "size": "1"}, {"name": "b", "size": "2"}],
    )

    widgets = adapter.widgets(response)

    assert isinstance(widgets[1], TableWidget)
    assert widgets[1].headers == ["name", "size"]
    assert widgets[1].rows == [["a", "1"], ["b", "2"]]


def test_exception_response_becomes_error_widget_with_traceback() -> None:
    adapter = ExceptionCommandResponseWidgetAdapter()
    response = ExceptionCommandResponse(content={"error": "boom", "traceback": "line 1\nline 2"})

    widgets = adapter.widgets(response)

    assert len(widgets) == 1
    assert isinstance(widgets[0], ErrorWidget)
    assert widgets[0].message == "boom"
    assert widgets[0].traceback == "line 1\nline 2"


def test_welcome_response_renders_only_the_hero_body() -> None:
    adapter = WelcomeCommandResponseWidgetAdapter()
    response = WelcomeCommandResponse(content={"hero": "Hello there"})

    widgets = adapter.widgets(response)

    assert len(widgets) == 1
    assert isinstance(widgets[0], TextWidget)
    assert widgets[0].heading == ""
    assert widgets[0].body == "Hello there"


def test_grid_response_becomes_heading_plus_grid_widget() -> None:
    adapter = GridCommandResponseWidgetAdapter()
    response = GridCommandResponse(
        content={
            "columns": 3,
            "rows": 2,
            "slot_width": 20,
            "slot_height": 5,
            "operation_enabled": True,
            "pinned_enabled": True,
        },
    )

    widgets = adapter.widgets(response)

    assert isinstance(widgets[0], TextWidget)
    assert widgets[0].heading == "Presentation Grid"
    assert isinstance(widgets[1], GridWidget)
    assert widgets[1].columns == 3
    assert widgets[1].rows == 2
    assert widgets[1].slot_width == 20
    assert widgets[1].slot_height == 5
    assert widgets[1].operation_enabled is True
    assert widgets[1].pinned_enabled is True


def test_grid_response_defaults_bands_to_disabled() -> None:
    adapter = GridCommandResponseWidgetAdapter()
    response = GridCommandResponse(content={})

    widgets = adapter.widgets(response)

    assert widgets[1].operation_enabled is False
    assert widgets[1].pinned_enabled is False
