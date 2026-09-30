from abc import ABC, abstractmethod
import json
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.adapter.loader import ResponseWidgetAdapterLoader
from ontobdc.cli.adapter.surface import (
    BorderlessTerminalSurfaceRenderer,
    TerminalSurfaceRenderer,
)
from ontobdc.cli.domain.port.renderer import (
    CommandResponseRendererPort,
    ResponseWidgetLoaderPort,
    TerminalStylePort,
    TerminalSurfacePort,
)
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.terminal_color import CheckOutcomeBadge


class ResponseWidgetLoaderAdapter(ResponseWidgetLoaderPort):
    """
    Exposes the response widget adapter loader through the loader port.
    """
    def __init__(self, loader: Optional[ResponseWidgetAdapterLoader] = None) -> None:
        self._loader: ResponseWidgetAdapterLoader = (
            loader or ResponseWidgetAdapterLoader()
        )

    def widgets(self, response: CommandResponse) -> List[Any]:
        return self._loader.get(response).widgets(response)


class TerminalSurfaceAdapter(TerminalSurfacePort):
    """
    Exposes the terminal surface renderer through the surface port.
    """
    def render(self, body_markdown: str, theme: str) -> str:
        return TerminalSurfaceRenderer.select_and_render(
            body_markdown=body_markdown,
            renderer=TerminalSurfaceRenderer(theme=theme),
        )


class BorderlessTerminalSurfaceAdapter(TerminalSurfacePort):
    """
    Exposes the borderless terminal surface renderer through the surface port.

    Selected in place of TerminalSurfaceAdapter when the caller's real
    display width cannot be trusted -- see
    BorderlessTerminalSurfaceRenderer's own docstring for why that makes
    the framed box the wrong choice.
    """
    def render(self, body_markdown: str, theme: str) -> str:
        # Called on the subclass, not TerminalSurfaceRenderer itself: with
        # body_markdown given, select_and_render delegates to
        # cls.with_content_surface, and cls is whichever class this was
        # called on -- calling it on the base class would silently build a
        # framed TerminalSurfaceRenderer no matter what renderer= says.
        return BorderlessTerminalSurfaceRenderer.select_and_render(
            body_markdown=body_markdown,
            renderer=BorderlessTerminalSurfaceRenderer(theme=theme),
        )


class PlainTerminalStyle(TerminalStylePort):
    """
    Null-object style used when no terminal styling is available.
    """
    def badge(self, severity: str) -> str:
        return ""

    def dim(self, text: str) -> str:
        return text


class MarkdownDocument:
    """
    Accumulator for the markdown lines produced by the widget strategies.
    """
    _FENCE: str = "```"

    def __init__(self) -> None:
        self._lines: List[str] = []

    def line(self, text: str = "") -> None:
        self._lines.append(text)

    def extend(self, texts: List[str]) -> None:
        self._lines.extend(texts)

    def blank(self) -> None:
        self._lines.append("")

    def heading(self, level: int, text: str) -> None:
        self._lines.append(f"{'#' * level} {text}")

    def fence(self, body: List[str]) -> None:
        self._lines.append(self._FENCE)
        self._lines.extend(body)
        self._lines.append(self._FENCE)
        self._lines.append("")

    def table(self, headers: List[str], rows: List[List[Any]]) -> None:
        safe_headers: List[str] = [self.cell(header) for header in headers]
        self._lines.append(f"| {' | '.join(safe_headers)} |")
        self._lines.append(f"| {' | '.join('---' for _ in safe_headers)} |")
        for row in rows:
            cells: List[str] = [self.cell(value) for value in row]
            cells.extend("" for _ in range(len(safe_headers) - len(cells)))
            self._lines.append(f"| {' | '.join(cells[:len(safe_headers)])} |")
        self._lines.append("")

    def to_text(self) -> str:
        return "\n".join(self._lines).rstrip("\n")

    @staticmethod
    def cell(value: Any) -> str:
        text: str = MarkdownDocument.text_of(value)
        return text.replace("\\", "\\\\").replace("|", "\\|")

    @staticmethod
    def text_of(value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\n", " ").strip()


class WidgetMarkdownStrategy(ABC):
    """
    Base strategy converting one widget type into markdown lines.
    """
    WIDGET_TYPE: str = ""
    _RENDER_WIDTH: int = 180

    @abstractmethod
    def write(self, widget: Any, document: MarkdownDocument) -> None:
        """
        Append the markdown representation of the widget to the document.
        """
        ...

    @staticmethod
    def attribute(widget: Any, name: str, default: Any) -> Any:
        value: Any = getattr(widget, name, None)
        return default if value is None else value

    @staticmethod
    def items(widget: Any, name: str) -> List[Any]:
        return list(WidgetMarkdownStrategy.attribute(widget, name, []))

    def rendered_lines(self, widget: Any, width: Optional[int] = None) -> List[str]:
        render = getattr(widget, "render", None)
        if not callable(render):
            return []
        try:
            rendered: List[Any] = list(render(width or self._RENDER_WIDTH) or [])
            return [str(line) for line in rendered]
        except Exception as exception:
            return [
                "```",
                f"<render-error {type(exception).__name__}: {exception}>",
                "```",
            ]

    def write_indented(self, lines: List[str], document: MarkdownDocument) -> None:
        for line in lines:
            document.line(line if line.startswith("```") else f" {line}")


class TableWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a table widget as a pipe table followed by one card per row.
    """
    WIDGET_TYPE: str = "TableWidget"

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        headers: List[Any] = self.items(widget, "headers")
        rows: List[List[Any]] = [list(row) for row in self.items(widget, "rows")]
        if not headers:
            return
        document.table([str(header) for header in headers], rows)
        if rows:
            self._write_details(headers, rows, document)

    def _write_details(
        self,
        headers: List[Any],
        rows: List[List[Any]],
        document: MarkdownDocument,
    ) -> None:
        document.heading(2, "DETAILS")
        document.blank()
        for row in rows:
            first: Any = row[0] if row else ""
            document.heading(4, MarkdownDocument.text_of(first) or "—")
            for index, header in enumerate(headers[1:], start=1):
                value: Any = row[index] if index < len(row) else ""
                label: str = str(header).upper()
                document.line(f"- {label}: {MarkdownDocument.text_of(value)}")
            document.blank()


class KeyValueWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a key/value widget as a label line or as one bullet per pair.
    """
    WIDGET_TYPE: str = "KeyValueWidget"

    def __init__(self, style: TerminalStylePort) -> None:
        self._style: TerminalStylePort = style

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        pairs: List[Any] = self.items(widget, "pairs")
        if not pairs:
            return
        if len(pairs) == 1:
            key, value = self._pair_of(pairs[0])
            document.line(f"{key.upper()}  {value}")
            document.blank()
            return
        for pair in pairs:
            self._write_pair(pair, document)

    def _write_pair(self, pair: Any, document: MarkdownDocument) -> None:
        key, value = self._pair_of(pair)
        value_lines: List[str] = value.split("\n")
        document.line(f"- {key.upper()}: {value_lines[0].strip()}")
        for detail in value_lines[1:]:
            self._write_detail(detail.strip(), document)
        document.blank()

    def _write_detail(self, detail: str, document: MarkdownDocument) -> None:
        if not detail:
            return
        label, separator, rest = detail.partition(":")
        styled: str = (
            f"{label}:{self._style.dim(rest)}"
            if separator
            else self._style.dim(detail)
        )
        document.line(f"\t{styled}")

    @staticmethod
    def _pair_of(pair: Any) -> Tuple[str, str]:
        values: List[Any] = list(pair) if isinstance(pair, (list, tuple)) else [pair]
        key: str = str(values[0]).strip()
        value: Any = values[1] if len(values) > 1 else ""
        return key, "" if value is None else str(value).strip()


class CodeBlockWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a code block widget as a fenced block.
    """
    WIDGET_TYPE: str = "CodeBlockWidget"

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        text: str = str(self.attribute(widget, "text", ""))
        if text:
            document.fence(text.splitlines())


class ErrorWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders an error widget as a fenced message plus its traceback.
    """
    WIDGET_TYPE: str = "ErrorWidget"

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        message: str = str(self.attribute(widget, "message", ""))
        if not message:
            return
        body: List[str] = message.splitlines()
        body.extend(self._traceback_lines(widget))
        document.fence(body)

    def _traceback_lines(self, widget: Any) -> List[str]:
        traceback: Any = getattr(widget, "traceback", None)
        if isinstance(traceback, (list, tuple)):
            return [str(line) for line in traceback if line is not None]
        if isinstance(traceback, str) and traceback.strip():
            return traceback.splitlines()
        return []


class HealthCheckWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a health check listing as one badged line per check.

    Each line is emitted verbatim — with the single leading space the
    markdown tile reads as "do not wrap this" — because the badge is an
    ANSI sequence and the paragraph wrapper measures those escape
    characters as if a reader could see them.
    """
    WIDGET_TYPE: str = "HealthCheckWidget"
    VERBATIM_PREFIX: str = " "

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        checks: List[Any] = self.items(widget, "checks")
        if not checks:
            return

        check: Any
        for check in checks:
            label, passed = self._check_of(check)
            if not label:
                continue

            document.line(
                f"{self.VERBATIM_PREFIX}{CheckOutcomeBadge.render(passed)}  {label}"
            )
            document.blank()

    @staticmethod
    def _check_of(check: Any) -> Tuple[str, bool]:
        values: List[Any] = (
            list(check) if isinstance(check, (list, tuple)) else [check]
        )
        label: str = str(values[0]).strip() if values else ""
        passed: bool = bool(values[1]) if len(values) > 1 else False

        return label, passed


class GridWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a grid widget as a fenced JSON block with its structural numbers.
    """
    WIDGET_TYPE: str = "GridWidget"
    _DEFAULTS: Dict[str, Any] = {
        "columns": 1,
        "rows": 1,
        "slot_width": 20,
        "slot_height": 5,
        "operation_enabled": False,
        "pinned_enabled": False,
    }

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        payload: Dict[str, Any] = {
            name: type(default)(self.attribute(widget, name, default))
            for name, default in self._DEFAULTS.items()
        }
        document.fence(json.dumps(payload, indent=2).splitlines())


class GraphWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a graph widget as node and edge tables plus its drawn graph.
    """
    WIDGET_TYPE: str = "GraphWidget"

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        self._write_section(
            document,
            "Nodes",
            ["ID", "Label"],
            [
                [node.get("id", ""), node.get("label", node.get("id", ""))]
                for node in self.items(widget, "nodes")
                if isinstance(node, dict)
            ],
        )
        self._write_section(
            document,
            "Edges",
            ["Source", "Target", "Label"],
            [
                [edge.get("source", ""), edge.get("target", ""), edge.get("label", "")]
                for edge in self.items(widget, "edges")
                if isinstance(edge, dict)
            ],
        )
        drawn: List[str] = self.rendered_lines(widget)
        if drawn:
            document.heading(3, "Graph")
            self.write_indented(drawn, document)
            document.blank()

    def _write_section(
        self,
        document: MarkdownDocument,
        heading: str,
        headers: List[str],
        rows: List[List[Any]],
    ) -> None:
        if not rows:
            return
        document.heading(3, heading)
        document.table(headers, rows)


class TreeWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders a tree widget by keeping its pre-drawn guide lines untouched.
    """
    WIDGET_TYPE: str = "TreeWidget"
    _SPACER_LINE: str = " "

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        document.line(self._SPACER_LINE)
        self.write_indented(self.rendered_lines(widget), document)
        document.line(self._SPACER_LINE)


class FallbackWidgetMarkdownStrategy(WidgetMarkdownStrategy):
    """
    Renders any other widget through its own render, or as a JSON dump.
    """
    _FALLBACK_WIDTH: int = 70

    def write(self, widget: Any, document: MarkdownDocument) -> None:
        rendered: List[str] = self.rendered_lines(widget, self._FALLBACK_WIDTH)
        if rendered:
            document.extend(rendered)
            document.blank()
            return
        document.fence(self._payload_lines(widget))

    def _payload_lines(self, widget: Any) -> List[str]:
        try:
            payload: Any = self._payload_of(widget)
            return json.dumps(payload, indent=2, default=str).splitlines()
        except Exception:
            return [repr(widget)]

    @staticmethod
    def _payload_of(widget: Any) -> Any:
        to_dict = getattr(widget, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        if isinstance(widget, dict):
            return widget
        if hasattr(widget, "__dict__"):
            return {
                name: value
                for name, value in vars(widget).items()
                if not name.startswith("_")
            }
        return {"value": repr(widget)}


class WidgetMarkdownStrategyFactory:
    """
    Resolves the markdown strategy that matches a widget type.
    """
    def __init__(self, style: TerminalStylePort) -> None:
        strategies: List[WidgetMarkdownStrategy] = [
            TableWidgetMarkdownStrategy(),
            KeyValueWidgetMarkdownStrategy(style),
            CodeBlockWidgetMarkdownStrategy(),
            ErrorWidgetMarkdownStrategy(),
            HealthCheckWidgetMarkdownStrategy(),
            GridWidgetMarkdownStrategy(),
            GraphWidgetMarkdownStrategy(),
            TreeWidgetMarkdownStrategy(),
        ]
        self._by_type: Dict[str, WidgetMarkdownStrategy] = {
            strategy.WIDGET_TYPE: strategy for strategy in strategies
        }
        self._fallback: WidgetMarkdownStrategy = FallbackWidgetMarkdownStrategy()

    def for_widget(self, widget: Any) -> WidgetMarkdownStrategy:
        return self._by_type.get(type(widget).__name__, self._fallback)


class ResponsePresentationPolicy:
    """
    Single source for the UX theme and the severity of a response type.
    """
    _BY_RESPONSE: Dict[str, Tuple[str, str]] = {
        "ExceptionCommandResponse": ("error", "ERROR"),
        "HealthCheckCommandResponse": ("info", "INFO"),
        "HelpCommandResponse": ("info", "INFO"),
        "RunCommandResponse": ("neutral", "RUN"),
    }
    _DEFAULT: Tuple[str, str] = ("ontobdc", "INFO")

    def theme_for(self, response: CommandResponse) -> str:
        return self._presentation_of(response)[0]

    def severity_for(self, response: CommandResponse) -> str:
        severity: Any = getattr(response, "severity", None)
        if severity is None:
            return self._presentation_of(response)[1]
        return str(getattr(severity, "value", severity))

    def _presentation_of(self, response: CommandResponse) -> Tuple[str, str]:
        for base in type(response).__mro__:
            presentation: Optional[Tuple[str, str]] = self._BY_RESPONSE.get(
                base.__name__
            )
            if presentation is not None:
                return presentation
        return self._DEFAULT


class ResponseMarkdownComposer:
    """
    Lowers a response and its widgets into a single markdown document.
    """
    _HEADING_WIDGET_TYPE: str = "TextWidget"

    def __init__(
        self,
        widget_loader: ResponseWidgetLoaderPort,
        strategies: WidgetMarkdownStrategyFactory,
        policy: ResponsePresentationPolicy,
        style: TerminalStylePort,
    ) -> None:
        self._widget_loader: ResponseWidgetLoaderPort = widget_loader
        self._strategies: WidgetMarkdownStrategyFactory = strategies
        self._policy: ResponsePresentationPolicy = policy
        self._style: TerminalStylePort = style

    # Widgets that draw their own geometry and are wider than the frame's
    # inner width. Fitting one to the frame truncates it, and wrapping it
    # destroys the alignment that is the whole of what it says, so it is
    # composed apart and printed below the frame instead.
    UNFRAMED_WIDGET_TYPES: ClassVar[Tuple[str, ...]] = ("TreeWidget",)

    def compose(self, response: CommandResponse) -> str:
        """
        Return the whole response as markdown, framed part and all.
        """
        framed: str
        unframed: str
        framed, unframed = self.compose_parts(response)
        if not unframed.strip():
            return framed

        return f"{framed}\n{unframed}"

    def compose_parts(self, response: CommandResponse) -> Tuple[str, str]:
        """
        Return what belongs inside the frame, and what belongs below it.
        """
        title: str = str(response.title or "").strip()
        document: MarkdownDocument = MarkdownDocument()
        unframed_document: MarkdownDocument = MarkdownDocument()
        self._write_heading(response, title, document)
        for widget in self._content_widgets(response, title):
            target: MarkdownDocument = document
            if type(widget).__name__ in self.UNFRAMED_WIDGET_TYPES:
                target = unframed_document

            self._strategies.for_widget(widget).write(widget, target)

        return document.to_text(), unframed_document.to_text()

    def _write_heading(
        self,
        response: CommandResponse,
        title: str,
        document: MarkdownDocument,
    ) -> None:
        if not title:
            return
        badge: str = self._style.badge(self._policy.severity_for(response))
        document.line(f"{badge} # {title}" if badge else f"# {title}")
        document.blank()
        description: str = str(response.description or "").strip()
        if description:
            document.line(description)
            document.blank()

    def _content_widgets(self, response: CommandResponse, title: str) -> List[Any]:
        widgets: List[Any] = self._widget_loader.widgets(response)
        return [
            widget
            for widget in widgets
            if not self._is_duplicate_heading(widget, title)
        ]

    def _is_duplicate_heading(self, widget: Any, title: str) -> bool:
        if not title or type(widget).__name__ != self._HEADING_WIDGET_TYPE:
            return False
        heading: str = str(getattr(widget, "heading", "") or "").strip()
        return heading in (f"# {title}", title)


class RenderMode(ABC):
    """
    Base output mode able to render a response to the console.
    """
    @abstractmethod
    def render(self, response: CommandResponse) -> None:
        """
        Render the response to the console.
        """
        ...


class PrintedRenderMode(RenderMode):
    """
    Output mode that prints the response's own representation.
    """
    def render(self, response: CommandResponse) -> None:
        print(response)


class RichRenderMode(RenderMode):
    """
    Output mode that frames the response markdown in the terminal surface.
    """
    def __init__(
        self,
        composer: ResponseMarkdownComposer,
        surface: TerminalSurfacePort,
        policy: ResponsePresentationPolicy,
    ) -> None:
        self._composer: ResponseMarkdownComposer = composer
        self._surface: TerminalSurfacePort = surface
        self._policy: ResponsePresentationPolicy = policy

    def render(self, response: CommandResponse) -> None:
        framed: str
        unframed: str
        framed, unframed = self._composer.compose_parts(response)
        output: str = self._surface.render(
            body_markdown=framed,
            theme=self._policy.theme_for(response),
        )
        unframed_lines: List[str] = self._trimmed(unframed)
        if not unframed_lines:
            print(output, end="" if output.endswith("\n") else "\n")
            return

        # One blank line above what is drawn under the frame and one
        # below, so it reads as its own thing rather than as something
        # that fell out of the frame. The block is stripped of the blank
        # lines it carries of its own, and so is the frame's own trailing
        # run, so each gap is exactly the one line printed here.
        print(output.rstrip("\n"))
        print()
        print("\n".join(unframed_lines))
        print()

    @staticmethod
    def _trimmed(block: str) -> List[str]:
        """
        Return the block's lines without the blank ones that bracket it.

        A widget composed for the frame opens and closes with a spacer of
        its own, which is the frame's breathing room, not this one's.
        """
        lines: List[str] = block.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        return lines


class CommandResponseRenderAdapter(CommandResponseRendererPort):
    """
    Renders a command response in the output mode requested by the CLI.

    The rich mode is only available when a widget loader and a terminal
    surface are supplied; the json and html modes are always available.
    """
    _RENDER_TYPES: Tuple[str, ...] = ("json", "rich", "html")

    def __init__(
        self,
        widget_loader: Optional[ResponseWidgetLoaderPort] = None,
        surface: Optional[TerminalSurfacePort] = None,
        style: Optional[TerminalStylePort] = None,
    ) -> None:
        self._policy: ResponsePresentationPolicy = ResponsePresentationPolicy()
        self._style: TerminalStylePort = style or PlainTerminalStyle()
        self._composer: Optional[ResponseMarkdownComposer] = (
            ResponseMarkdownComposer(
                widget_loader,
                WidgetMarkdownStrategyFactory(self._style),
                self._policy,
                self._style,
            )
            if widget_loader is not None
            else None
        )
        self._modes: Dict[str, RenderMode] = {
            "json": PrintedRenderMode(),
            "html": PrintedRenderMode(),
        }
        if self._composer is not None and surface is not None:
            self._modes["rich"] = RichRenderMode(self._composer, surface, self._policy)

    def render(self, response: CommandResponse, render_type: str) -> None:
        if render_type not in self._RENDER_TYPES:
            raise ValueError(f"Unknown render type: {render_type}")

        mode: Optional[RenderMode] = self._modes.get(render_type)
        if mode is None:
            raise ValueError(
                "Rich rendering requires a widget loader and a terminal surface."
            )
        mode.render(response)

    def response_to_markdown(self, response: CommandResponse) -> str:
        if self._composer is None:
            raise ValueError("Markdown rendering requires a widget loader.")
        return self._composer.compose(response)

    def ux_theme_for(self, response: CommandResponse) -> str:
        return self._policy.theme_for(response)
