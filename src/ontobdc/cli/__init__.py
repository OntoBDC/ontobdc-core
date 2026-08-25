
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.adapter.logger import BaseLoggerAdapter, InLineLogger, NullLogRepository, StandardConsoleLogger
from ontobdc.cli.adapter.terminal import prompt_choice, prompt_raw_text
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.logger import LogLevel, LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort, PromptRawTextAwarePort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    HelpCommandResponse,
    InteractiveCommandResponse,
)
from ontobdc.shared.adapter.loader import ParameterLoader
from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.shared.facade.adapter.logger import (
    clear_active_log_repository,
    set_active_log_repository,
)
from ontobdc.cli.adapter.loader import ResponseWidgetAdapterLoader

def main() -> None:
    """
    Main entry point for the ontobdc CLI.

    Parses command line arguments and dispatches to the appropriate handler.
    """
    incoming_args: List[str] = _parse_incoming_args()

    logger: Optional[LogRepositoryPort] = None
    try:
        render_type: str = 'rich'
        if "--json" in sys.argv:
            render_type = 'json'
        elif "--html" in sys.argv:
            render_type = 'html'

        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        logger = StandardConsoleLogger()
        if render_type == 'json':
            logger = NullLogRepository()
        elif render_type == 'rich':
            logger = InLineLogger()

        resolved_log_level: Optional[LogLevel]
        sanitized_incoming_args: List[str]
        resolved_log_level, sanitized_incoming_args = _consume_global_log_level(
            incoming_args
        )

        # Apply log threshold *before* exposing the logger through the
        # global broker so any consumer (including the capability success
        # logging path) reaches an already-configured instance.  When the
        # user omits --log-level we still want INFO messages to surface
        # on side-effecting capabilities, so we default to INFORMATIONAL
        # in that case instead of the base NOTICE default.
        if resolved_log_level is not None:
            _ = LogStrategyConfig(
                log_level=resolved_log_level,
                log_repository=logger,
            )
        else:
            if hasattr(logger, "set_log_level"):
                from ontobdc.cli.domain.model.logger import LogLevel as _LL
                logger.set_log_level(_LL.INFORMATIONAL)

        set_active_log_repository(logger)

        cli_command_run: CliCommandPort = CliCommandRunAdapter.make(
            sanitized_incoming_args,
            logger,
            defer_check=True,
        )

        if resolved_log_level is not None:
            request: Optional[Any] = getattr(cli_command_run, "_request", None)
            context: Optional[CliContextPort] = getattr(request, "context", None)
            if context is not None:
                context.set_parameter_value("log_level", resolved_log_level)

        if _PARAMETER_VALIDATOR.check(cli_command_run, sanitized_incoming_args, logger):
            if isinstance(cli_command_run, LoggerAwarePort):
                log_strategy_kwargs: Dict[str, Any] = {"log_repository": logger}
                if resolved_log_level is not None:
                    log_strategy_kwargs["log_level"] = resolved_log_level
                log_strategy = LogStrategyConfig(**log_strategy_kwargs)
                cli_command_run.set_log_strategy(log_strategy)

            if isinstance(cli_command_run, PromptChoiceAwarePort):
                cli_command_run.set_prompt_choice(prompt_choice)

            if isinstance(cli_command_run, PromptRawTextAwarePort):
                cli_command_run.set_prompt_raw_text(prompt_raw_text)

            response: CommandResponse = cli_command_run.run()
            if not silent and not isinstance(
                response,
                InteractiveCommandResponse,
            ):
                _render_response(response, logger, render_type)

            sys.exit(0)

    except Exception as e:
        try:
            safe_render_type: str = render_type
        except NameError:
            safe_render_type = "rich"
        try:
            safe_silent: bool = silent
        except NameError:
            safe_silent = False
        safe_logger: LogRepositoryPort = (
            logger if logger is not None else NullLogRepository()
        )
        response: CommandResponse = ExceptionCommandResponse(
            title="Run",
            description="Command execution failed.",
            content={"error": str(e)},
        )
        if not safe_silent:
            _render_response(response, safe_logger, safe_render_type)

        sys.exit(1)
    finally:
        clear_active_log_repository()


def _parse_incoming_args() -> List[str]:
    """
    Parse command line arguments.
    """
    return [
        arg
        for arg in sys.argv[1:]
        if arg not in ["--json", "--rich", "--html", "--silent", "-s"]
    ]


def _consume_global_log_level(
    args: List[str],
) -> Tuple[Optional[LogLevel], List[str]]:
    """Consume every ``--log-level`` flag and its value from *args* before
    command routing runs.

    This is the **global stage-0 parser** for parameters that are valid for
    every command and must **disappear** from ``incoming_args`` before
    :class:`CliCommandRunAdapter.make` scans candidates via
    ``CliCommandPort.accepts(args)``.  Leaving ``--log-level`` in the
    argument vector at routing time would break the strict positional
    matching every command uses (``len(args)`` and token positions).

    The implementation deliberately **reuses** the stateless helpers on
    :class:`LogLevelStrategy` so the parser, normaliser, and validator
    live in a single canonical source of truth — no duplicated logic
    between ``main`` and the parameter-strategy pipeline.

    Returns:
        A 2-tuple ``(resolved_level, sanitized_args)`` where
        *resolved_level* is ``None`` when the user did not supply the flag
        and *sanitized_args* is a copy of *args* with every
        ``--log-level VALUE`` / ``--log-level=VALUE`` token stripped.
    """
    from ontobdc.cli.plugin.parameter.log_level import LogLevelStrategy as _LLS

    raw_level, sanitized_args = _LLS._consume(list(args))
    resolved_level: Optional[LogLevel] = None
    if raw_level is not None:
        resolved_level = _LLS._resolve(raw_level)
    return resolved_level, sanitized_args


class CliParameterValidationOrchestrator:
    """Orchestrates the binding and validation of CLI parameters before a
    command ``run()`` executes.

    This class groups the four tightly-coupled parameter-resolution steps
    that were previously loose module-level functions, keeping the CLI
    entry-point lean and the flow cohesive:

    1. *Explicit valued flags* are read from ``incoming_args`` and written
       to the ``CliContextPort`` (``--container urn:...`` becomes
       ``context["container"] = "urn:..."``).
    2. *Required parameter names* are harvested from the command's
       ``METADATA.arguments`` so parameter strategies that are not declared
       by the command are skipped (they would run, but write to context
       keys the command never reads -- a waste at best, misleading at
       worst).
    3. Every ``ParameterStrategy`` declared by the ``ParameterLoader`` and
       matched to the required names is *configured* for this environment
       (logger, prompt callbacks) and then *executed* against the context
       (the "implicit parameter" stage that derives values from defaults,
       env vars, project config, or resolved paths).
    4. The command's own ``check()`` runs last -- if it returns False the
       orchestrator raises ``CliCommandArgumentException`` so the caller
       (``main``) can print the failure and exit.

    The orchestrator is stateless: every input is passed as an argument and
    the same instance is safe to reuse across multiple command runs.
    """

    def check(
        self,
        cli_command_run: CliCommandPort,
        incoming_args: List[str],
        logger: LogRepositoryPort,
        parameter_loader: Optional[ParameterLoader] = None,
    ) -> bool:
        """Return True when ``cli_command_run`` has valid inputs to execute.

        Raises :class:`CliCommandArgumentException` whenever parameter
        binding ran but the command's own ``check()`` still rejects the
        context -- this is the public entry-point the CLI ``main()`` calls
        before dispatching to :meth:`CliCommandPort.run`.
        """
        request: Optional[Any] = getattr(cli_command_run, "_request", None)
        context: Optional[CliContextPort] = getattr(request, "context", None)
        if context is None:
            return True

        self.apply_explicit_parameter_values(cli_command_run, incoming_args, context)

        if parameter_loader is None:
            parameter_loader = ParameterLoader(logger=logger)

        parameter_strategies: List[Any] = parameter_loader.get_all()
        required_parameter_names: Set[str] = self.resolve_required_parameter_names(
            cli_command_run
        )

        for parameter_strategy in parameter_strategies:
            parameter_name: Optional[str] = self.resolve_parameter_name(parameter_strategy)
            if parameter_name is None or parameter_name not in required_parameter_names:
                continue

            self.configure_parameter_strategy(parameter_strategy, logger)
            parameter_strategy.execute(context)

        if not cli_command_run.check():
            raise CliCommandArgumentException(
                f"Invalid command arguments: {incoming_args}"
            )

        return True

    def apply_explicit_parameter_values(
        self,
        cli_command_run: CliCommandPort,
        incoming_args: List[str],
        context: CliContextPort,
    ) -> None:
        """Copy every valued long-flag (``--foo value``) declared by the
        command's ``METADATA`` into ``context`` as snake_case keys.

        Bails silently when the command declares no ``arguments`` list, no
        valued entries, or when the user did not supply a value token after
        the flag -- the later ``check()`` stage is responsible for turning
        missing-but-required values into user-visible errors.
        """
        metadata: Optional[Any] = getattr(cli_command_run, "METADATA", None)
        arguments: Any = getattr(metadata, "arguments", [])
        if not isinstance(arguments, list):
            return

        argument_definition: Any
        for argument_definition in arguments:
            if not isinstance(argument_definition, dict):
                continue
            if not bool(argument_definition.get("valued", False)):
                continue

            accepts: Any = argument_definition.get("accepts", [])
            if not isinstance(accepts, list):
                continue

            accepted_flag: Any
            for accepted_flag in accepts:
                if not isinstance(accepted_flag, str) or not accepted_flag.startswith("--"):
                    continue
                if accepted_flag not in incoming_args:
                    continue

                accepted_flag_index: int = incoming_args.index(accepted_flag)
                next_index: int = accepted_flag_index + 1
                if next_index >= len(incoming_args):
                    return

                context.set_parameter_value(
                    accepted_flag[2:].replace("-", "_"),
                    incoming_args[next_index],
                )
                break

    def resolve_required_parameter_names(
        self,
        cli_command_run: CliCommandPort,
    ) -> Set[str]:
        """Return the snake_case parameter keys the command's ``METADATA``
        declares as valued long-flags.

        Parameter strategies whose ``METADATA.name`` is not in this set are
        skipped during the implicit stage, which keeps the parameter
        pipeline deterministic and avoids leaking shared strategies into
        commands that never asked for them.
        """
        metadata: Optional[Any] = getattr(cli_command_run, "METADATA", None)
        arguments: Any = getattr(metadata, "arguments", [])
        if not isinstance(arguments, list):
            return set()

        required_parameter_names: Set[str] = set()
        argument_definition: Any
        for argument_definition in arguments:
            if not isinstance(argument_definition, dict):
                continue
            if not bool(argument_definition.get("valued", False)):
                continue

            accepts: Any = argument_definition.get("accepts", [])
            if not isinstance(accepts, list):
                continue

            accepted_flag: Any
            for accepted_flag in accepts:
                if not isinstance(accepted_flag, str) or not accepted_flag.startswith("--"):
                    continue
                required_parameter_names.add(accepted_flag[2:].replace("-", "_"))

        return required_parameter_names

    def resolve_parameter_name(self, parameter_strategy: Any) -> Optional[str]:
        """Return the normalized snake_case parameter name a parameter
        strategy wants to own, or ``None`` when the strategy has no
        ``METADATA.name``.
        """
        metadata: Optional[Any] = getattr(parameter_strategy, "METADATA", None)
        parameter_name: Any = getattr(metadata, "name", None)
        if not isinstance(parameter_name, str):
            return None

        normalized_parameter_name: str = parameter_name.strip()
        if not normalized_parameter_name:
            return None

        return normalized_parameter_name

    def configure_parameter_strategy(
        self,
        parameter_strategy: Any,
        logger: LogRepositoryPort,
    ) -> None:
        """Attach shared runtime callbacks (logger, interactive prompts)
        to a parameter strategy that declares support for them via the
        ``LoggerAwarePort`` / ``PromptChoiceAwarePort`` /
        ``PromptRawTextAwarePort`` marker ports.
        """
        if isinstance(parameter_strategy, LoggerAwarePort):
            parameter_strategy.set_log_strategy(
                LogStrategyConfig(
                    log_repository=logger,
                )
            )

        if isinstance(parameter_strategy, PromptChoiceAwarePort):
            parameter_strategy.set_prompt_choice(prompt_choice)

        if isinstance(parameter_strategy, PromptRawTextAwarePort):
            parameter_strategy.set_prompt_raw_text(prompt_raw_text)


_PARAMETER_VALIDATOR = CliParameterValidationOrchestrator()


def _render_response(
    response: CommandResponse,
    _logger: BaseLoggerAdapter,
    render_type: str,
) -> None:
    """
    Render a command response to the console.

    Supports JSON, rich, and HTML rendering.

    Args:
        response: The command response object to render
        render_type: The type of rendering to perform (e.g., 'json' or 'rich')
    """
    if render_type == 'json':
        _render_json_response(response)
    elif render_type == 'rich':
        _render_rich_response(response)
    elif render_type == 'html':
        _render_html_response(response)
    else:
        raise ValueError(f"Unknown render type: {render_type}")


def _render_json_response(response: CommandResponse) -> None:
    """
    Render a JSON command response to the console.
    
    Args:
        response: The command response object to render
    """
    _clear_terminal()
    print(response)


def _render_rich_response(response: CommandResponse) -> None:
    """
    Render a command response onto the terminal PresentationSurface.

    The output is framed by a single outer UX moldura (Unicode box-drawing)
    whose border color follows the active UX theme. The top border line is
    the "operation bar" — tiles placed inside the ``OperationRegion`` of
    the surface (logo, etc.) *open a cutout* in the top line and sit flush
    inside the frame, exactly like the HTML presentation layer's top
    operation bar. The body region is inner full-width and carries the
    rendered response content (heading, description, widgets/tables). Tiles
    in the ``PinnedRegion`` open a matching cutout in the bottom border
    line for chrome/status elements.

    Args:
        response: The command response object to render
    """
    # Local imports to avoid top-level circular import chain:
    # cli/__init__.py -> widget/python.py (no problem)  but  legacy surface
    # imports shared/adapter/loader which imports facade/port/context which
    # imports cli/domain/port/context  →  cycles back to cli/__init__.py
    # before this module finishes loading.
    from ontobdc.cli.adapter.loader import ResponseWidgetAdapterLoader as _RWAL
    from ontobdc.view.adapter.terminal.surface_renderer import (
        TerminalSurfaceRenderer as _TSR,
    )
    from ontobdc.view.component.widget.python import TextWidget as _TW

    body_markdown: str = _response_to_markdown(
        response,
        response_loader_cls=_RWAL,
        text_widget_cls=_TW,
        widget_protocol=None,
    )

    theme: str = _ux_theme_for(response)
    output: str = _TSR.select_and_render(
        body_markdown=body_markdown,
        renderer=_TSR(theme=theme),
    )
    print(output, end="" if output.endswith("\n") else "\n")


def _ux_theme_for(response: CommandResponse) -> str:
    from ontobdc.cli.domain.response.command import ExceptionCommandResponse

    if isinstance(response, ExceptionCommandResponse):
        return "error"
    return "default"


def _default_severity_for_response(response: CommandResponse) -> Optional[str]:
    """Mirror of ``BaseResponseWidgetAdapter._default_heading_severity``.

    Duplicated here intentionally to avoid pulling the adapter layer into
    a helper that runs *before* widget decomposition — this function is
    single-purpose: convert a CommandResponse type into a string-level
    severity suitable for ``severity_badge(...)``.  Keep the two
    policies in sync manually if the rules ever change.
    """
    from ontobdc.cli.domain.response.command import (
        ExceptionCommandResponse,
        HelpCommandResponse,
    )

    if isinstance(response, ExceptionCommandResponse):
        return "ERROR"
    if isinstance(response, HelpCommandResponse):
        return "INFO"
    return "INFO"


def _response_to_markdown(
    response: CommandResponse,
    *,
    response_loader_cls: Any,
    text_widget_cls: Any,
    widget_protocol: Any,
) -> str:
    title: str = str(response.title or "").strip()
    description: str = str(response.description or "").strip()
    from ontobdc.shared.adapter.terminal_color import severity_badge

    severity: Optional[object] = getattr(response, "severity", None)
    if severity is None:
        severity = _default_severity_for_response(response)
    badge: str = (
        severity_badge(severity, fallback=None) if severity is not None else ""
    )

    loader = response_loader_cls()
    adapter = loader.get(response)
    widgets: List[Any] = adapter.widgets(response)

    _heading_prefix: str = f"# {title}" if title else ""

    def _is_duplicate_top_level_heading_widget(w: Any) -> bool:
        if not isinstance(w, text_widget_cls):
            return False
        w_heading: str = (getattr(w, "heading", "") or "").lstrip()
        if not title:
            return False
        if w_heading.lstrip() == _heading_prefix:
            return True
        if w_heading.strip() == str(title).strip():
            return True
        return False

    content_widgets: List[Any] = [w for w in widgets if not _is_duplicate_top_level_heading_widget(w)]

    lines: List[str] = []
    if title:
        heading_line: str = f"# {title}"
        if badge:
            heading_line = f"{badge} {heading_line}"
        lines.append(heading_line)
        lines.append("")
        if description:
            lines.append(description)
            lines.append("")

    def _escape_pipe_cell(value: Any) -> str:
        text: str = str(value).replace("\n", " ").strip()
        return text.replace("\\", "\\\\").replace("|", "\\|")

    for widget in content_widgets:
        wtype: str = type(widget).__name__
        # --- TableWidget → emit a pipe table so the new terminal markdown
        # renderer paints it as an inner grid with cyan bold headers.  This is the
        # crucial fix: previously we do NOT fall back to TableWidget.render() which emits
        # raw space-padded columns that the markdown parser ignores.
        if wtype == "TableWidget":
            headers: List[str] = list(getattr(widget, "headers", []) or [])
            rows_list: List[List[Any]] = list(getattr(widget, "rows", []) or [])
            if headers:
                safe_headers: List[str] = [_escape_pipe_cell(h) for h in headers]
                lines.append("| " + " | ".join(safe_headers) + " |")
                lines.append("| " + " | ".join("---" for _ in safe_headers) + " |")
                for row in rows_list:
                    cells: List[str] = [
                        _escape_pipe_cell(c if c is not None else "") for c in row]
                    while len(cells) < len(safe_headers):
                        cells.append("")
                    lines.append("| " + " | ".join(cells[: len(safe_headers)]) + " |")
                lines.append("")

                # --- DETAILS → one card per record with every field spelled
                # out in full (no column-width budget to share, so nothing
                # here is ever wrapped or cut). Generic to any TableWidget,
                # not just storage containers, so every list-shaped CLI
                # response gets a lossless detail view under its table.
                # Heading level matches CONTAINERS-style list headings (## )
                # so DETAILS sits at the same left alignment.
                if rows_list:
                    lines.append("## DETAILS")
                    lines.append("")
                    for row in rows_list:
                        first_value: Any = row[0] if row else ""
                        card_title: str = str(
                            first_value if first_value is not None else ""
                        ).replace("\n", " ").strip() or "—"
                        lines.append(f"#### {card_title}")
                        for col_index, header in enumerate(headers):
                            cell_value: Any = row[col_index] if col_index < len(row) else ""
                            cell_text: str = str(
                                cell_value if cell_value is not None else ""
                            ).replace("\n", " ").strip()
                            lines.append(f"- {str(header).upper()}: {cell_text}")
                        lines.append("")
            continue

        if wtype == "KeyValueWidget":
            pairs: List[Any] = list(getattr(widget, "pairs", []) or [])
            if pairs:
                n_pairs: int = len(pairs)
                if n_pairs == 1:
                    # Singleton KV record (e.g. version command): render the
                    # key as an UPPER CASE label + the value on the same line
                    # instead of the generic two-column pipe table.  This
                    # matches the "a version command output should not live
                    # inside a KEY/VALUE table" UX expectation from InfoBIM
                    # (and, transitively, OntoBDC's own short commands).
                    try:
                        k, v = pairs[0][0], pairs[0][1]
                    except Exception:
                        k, v = str(pairs[0]), ""
                    label: str = str(k).upper().strip()
                    value: str = "" if v is None else str(v).strip()
                    lines.append(f"{label}  {value}")
                    lines.append("")
                    continue
                # Multi-pair records: render as a compact label/value block,
                # one pair per line, key right-padded to the longest key so
                # all value columns start at the same column.  Never emit the
                # generic pipe table grid (neutral / cyan separators) because
                # small descriptive KV blocks read cleaner as plain label +
                # value alignment than as a drawn table chrome.
                max_key_w: int = max(1, max(len(str(p[0])) for p in pairs))
                for pair in pairs:
                    try:
                        k, v = pair[0], pair[1]
                    except Exception:
                        k, v = str(pair), ""
                    key_text: str = str(k).upper().strip()
                    value_text: str = "" if v is None else str(v).strip()
                    lines.append(f"{key_text:<{max_key_w}}  {value_text}")
                lines.append("")
            continue

        if wtype in ("CodeBlockWidget",):
            raw_text: str = str(getattr(widget, "text", "") or "")
            if raw_text:
                lines.append("```")
                lines.extend(raw_text.splitlines())
                lines.append("```")
                lines.append("")
            continue

        if wtype == "ErrorWidget":
            msg: str = str(getattr(widget, "message", "") or "")
            if msg:
                lines.append("```")
                lines.extend(msg.splitlines())
                extra: Any = getattr(widget, "traceback", None)
                if isinstance(extra, (list, tuple)):
                    lines.extend([str(line) for line in extra if line is not None])
                elif isinstance(extra, str) and extra.strip():
                    lines.extend(extra.splitlines())
                lines.append("```")
                lines.append("")
            continue

        if wtype == "GridWidget":
            # Legacy grid metadata payload: dump as a fenced JSON block so the
            # structural numbers are preserved without forcing the renderer to
            # re-implement the old terminal tile-grid drawing.
            payload: Dict[str, Any] = {
                "columns": int(getattr(widget, "columns", 1) or 1),
                "rows": int(getattr(widget, "rows", 1) or 1),
                "slot_width": int(getattr(widget, "slot_width", 20) or 20),
                "slot_height": int(getattr(widget, "slot_height", 5) or 5),
                "operation_enabled": bool(getattr(widget, "operation_enabled", False)),
                "pinned_enabled": bool(getattr(widget, "pinned_enabled", False)),
            }
            lines.append("```")
            lines.extend(json.dumps(payload, indent=2).splitlines())
            lines.append("```")
            lines.append("")
            continue

        # --- GraphWidget → emit the node list and edge list as pipe tables
        #      (nodes / edges) and then render the graph as inline code lines
        #      pre-padded so they look like a graph section without the ```
        #      fence.  Using a fence would force the graph lines to inherit the
        #      renderer's paragraph-wrap width (which doesn't have access to the
        #      terminal columns) and make the renderer cut the graph mid-box.
        if wtype == "GraphWidget":
            node_list: List[Any] = list(getattr(widget, "nodes", []) or [])
            edge_list: List[Any] = list(getattr(widget, "edges", []) or [])
            if node_list:
                lines.append("### Nodes")
                lines.append("| ID | Label |")
                lines.append("| --- | --- |")
                for n in node_list:
                    if isinstance(n, dict):
                        lines.append(
                            f"| {_escape_pipe_cell(n.get('id', ''))} "
                            f"| {_escape_pipe_cell(n.get('label', n.get('id', '')))} |"
                        )
                lines.append("")
            if edge_list:
                lines.append("### Edges")
                lines.append("| Source | Target | Label |")
                lines.append("| --- | --- | --- |")
                for e in edge_list:
                    if isinstance(e, dict):
                        lines.append(
                            f"| {_escape_pipe_cell(e.get('source', ''))} "
                            f"| {_escape_pipe_cell(e.get('target', ''))} "
                            f"| {_escape_pipe_cell(e.get('label', ''))} |"
                        )
                lines.append("")
            render_fn = getattr(widget, "render", None)
            rendered_graph: List[str] = []
            if callable(render_fn):
                try:
                    rendered_graph = list(render_fn(180) or [])
                except Exception as exc:  # noqa: BLE001 — keep CLI from failing
                    rendered_graph = [
                        "```",
                        f"<graph-render-error {type(exc).__name__}: {exc}>",
                        "```",
                    ]
            if rendered_graph:
                lines.append("### Graph")
                for gline in rendered_graph:
                    if gline.startswith("```"):
                        lines.append(str(gline))
                    else:
                        lines.append(" " + str(gline))
                lines.append("")
            continue

        # --- TreeWidget → emit the pre-drawn directory-tree lines verbatim
        #      (single leading space = don't reflow/reword-wrap them; the
        #      tree's own guide lines and indentation must survive as-is).
        if wtype == "TreeWidget":
            render_fn = getattr(widget, "render", None)
            rendered_tree: List[str] = []
            if callable(render_fn):
                try:
                    rendered_tree = list(render_fn(180) or [])
                except Exception as exc:  # noqa: BLE001 — keep CLI from failing
                    rendered_tree = [
                        "```",
                        f"<tree-render-error {type(exc).__name__}: {exc}>",
                        "```",
                    ]
            for tline in rendered_tree:
                if tline.startswith("```"):
                    lines.append(str(tline))
                else:
                    lines.append(" " + str(tline))
            lines.append("")
            continue

        # --- default (TextWidget and unknown) → fallback to widget.render(...)
        #      when available.  Container payloads that do not know how to
        #      self-render are dumped as a fenced JSON block to keep the CLI
        #      from exploding on legacy/unknown widget shapes.
        try:
            render_fn = getattr(widget, "render", None)
            if callable(render_fn):
                rendered: List[str] = render_fn(max(40, 70))
                lines.extend(rendered)
                lines.append("")
            else:
                lines.append("```")
                try:
                    as_text: str
                    if hasattr(widget, "to_dict") and callable(getattr(widget, "to_dict")):
                        as_text = json.dumps(getattr(widget, "to_dict")(), indent=2, default=str)
                    elif isinstance(widget, dict):
                        as_text = json.dumps(widget, indent=2, default=str)
                    else:
                        payload_dict: Dict[str, Any] = {
                            k: v for k, v in vars(widget).items()
                            if not k.startswith("_")
                        } if hasattr(widget, "__dict__") else {"value": repr(widget)}
                        as_text = json.dumps(payload_dict, indent=2, default=str)
                    lines.extend(as_text.splitlines())
                except Exception:
                    lines.append(repr(widget))
                lines.append("```")
                lines.append("")
        except Exception as exc:  # noqa: BLE001 — CLI must not crash on render fallback
            lines.append("```")
            lines.append(f"render-fallback-error: {type(exc).__name__}: {exc}")
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip()


def _ux_theme_for(response: CommandResponse) -> str:
    if isinstance(response, ExceptionCommandResponse):
        return "error"
    if isinstance(response, HelpCommandResponse):
        return "info"
    return "ontobdc"


def _render_html_response(response: CommandResponse) -> None:
    """
    Render a HTML command response to the console.
    
    Args:
        response: The command response object to render
    """
    print(response)


def _clear_terminal() -> None:
    """
    Clear the active terminal before rendering a new response.
    """
    subprocess.run(["clear"], check=False)
