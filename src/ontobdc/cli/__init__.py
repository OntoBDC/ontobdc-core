
import subprocess
import sys
from typing import Any, List, Optional, Set

from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.adapter.logger import BaseLoggerAdapter, InLineLogger, NullLogRepository, StandardConsoleLogger
from ontobdc.cli.adapter.old_terminal import prompt_choice, prompt_raw_text
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.logger import LogLevel, LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort, PromptRawTextAwarePort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.adapter.loader import ParameterLoader
from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.view.adapter.loader import ResponseMessageBoxAdapterLoader
from ontobdc.view.domain.port.response import ResponseMessageBoxAdapterPort
from ontobdc.view.plugin.render.rich.layout import RichMessageBoxLayout


def main() -> None:
    """
    Main entry point for the ontobdc CLI.
    
    Parses command line arguments and dispatches to the appropriate handler.
    """
    incoming_args: List[str] = _parse_incoming_args()

    try:
        render_type: str = 'rich'
        if "--json" in sys.argv:
            render_type = 'json'
        elif "--html" in sys.argv:
            render_type = 'html'

        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        logger: LogRepositoryPort = StandardConsoleLogger()
        if render_type == 'json':
            logger = NullLogRepository()
        elif render_type == 'rich':
            logger = InLineLogger()

        cli_command_run: CliCommandPort = CliCommandRunAdapter.make(
            incoming_args,
            logger,
            defer_check=True,
        )

        if _check_command(cli_command_run, incoming_args, logger):
            if isinstance(cli_command_run, LoggerAwarePort):
                log_strategy = LogStrategyConfig(
                    log_level=LogLevel.INFORMATIONAL,
                    log_repository=logger,
                )
                cli_command_run.set_log_strategy(log_strategy)

            if isinstance(cli_command_run, PromptChoiceAwarePort):
                cli_command_run.set_prompt_choice(prompt_choice)

            if isinstance(cli_command_run, PromptRawTextAwarePort):
                cli_command_run.set_prompt_raw_text(prompt_raw_text)

            response: CommandResponse = cli_command_run.run()
            if not silent:
                _render_response(response, logger, render_type)

            sys.exit(0)

    except Exception as e:
        response: CommandResponse = ExceptionCommandResponse(
            title="OntoBDC Run",
            description="Command execution failed.",
            content={"error": str(e)},
        )
        if not silent:
            _render_response(response, logger, render_type)

        sys.exit(1)


def _parse_incoming_args() -> List[str]:
    """
    Parse command line arguments.
    """
    return [arg for arg in sys.argv[1:] if arg not in ["--json", "--rich", "--html", "--silent", "-s"]]


def _check_command(
    cli_command_run: CliCommandPort,
    incoming_args: List[str],
    logger: LogRepositoryPort,
    parameter_loader: Optional[ParameterLoader] = None,
) -> bool:
    """
    Check if a command is valid and ready to execute.
    
    Args:
        cli_command_run: The CLI command runner instance
        incoming_args: The command line arguments
    
    Returns:
        True if the command is valid after parameter strategies run.
    """
    request: Optional[Any] = getattr(cli_command_run, "_request", None)
    context: Optional[CliContextPort] = getattr(request, "context", None)
    if context is None:
        return True

    _apply_explicit_parameter_values(cli_command_run, incoming_args, context)

    if parameter_loader is None:
        parameter_loader = ParameterLoader()

    parameter_strategies: List[Any] = parameter_loader.get_all()
    required_parameter_names: Set[str] = _resolve_required_parameter_names(cli_command_run)

    for parameter_strategy in parameter_strategies:
        parameter_name: Optional[str] = _resolve_parameter_name(parameter_strategy)
        if parameter_name is None or parameter_name not in required_parameter_names:
            continue

        _configure_parameter_strategy(parameter_strategy, logger)
        parameter_strategy.execute(context)

    if not cli_command_run.check():
        raise CliCommandArgumentException(f"Invalid command arguments: {incoming_args}")

    return True


def _apply_explicit_parameter_values(
    cli_command_run: CliCommandPort,
    incoming_args: List[str],
    context: CliContextPort,
) -> None:
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


def _resolve_required_parameter_names(cli_command_run: CliCommandPort) -> Set[str]:
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


def _resolve_parameter_name(parameter_strategy: Any) -> Optional[str]:
    metadata: Optional[Any] = getattr(parameter_strategy, "METADATA", None)
    parameter_name: Any = getattr(metadata, "name", None)
    if not isinstance(parameter_name, str):
        return None

    normalized_parameter_name: str = parameter_name.strip()
    if not normalized_parameter_name:
        return None

    return normalized_parameter_name


def _configure_parameter_strategy(parameter_strategy: Any, logger: LogRepositoryPort) -> None:
    if isinstance(parameter_strategy, LoggerAwarePort):
        parameter_strategy.set_log_strategy(
            LogStrategyConfig(
                log_level=LogLevel.INFORMATIONAL,
                log_repository=logger,
            )
        )

    if isinstance(parameter_strategy, PromptChoiceAwarePort):
        parameter_strategy.set_prompt_choice(prompt_choice)

    if isinstance(parameter_strategy, PromptRawTextAwarePort):
        parameter_strategy.set_prompt_raw_text(prompt_raw_text)


def _render_response(response: CommandResponse, _logger: BaseLoggerAdapter, render_type: str) -> None:
    """
    Render a command response to the console.
    
    Supports JSON, rich, and HTML rendering.

    Args:
        response: The command response object to render
        render_type: The type of rendering to perform (e.g., 'json' or 'rich')
    """
    def _resolve_render_type(render_type: str) -> str:
        if render_type == 'json':
            return _render_json_response
        elif render_type == 'rich':
            return _render_rich_response
        elif render_type == 'html':
            return _render_html_response
        else:
            raise ValueError(f"Unknown render type: {render_type}")
    
    render_function = _resolve_render_type(render_type)

    render_function(response)


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
    Render a rich command response to the console.
    
    Args:
        response: The command response object to render
    """
    view_loader: PluginLoaderPort = ResponseMessageBoxAdapterLoader()
    box_layout: ResponseMessageBoxAdapterPort = view_loader.get(response)

    print(box_layout.render(response, RichMessageBoxLayout()))


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
