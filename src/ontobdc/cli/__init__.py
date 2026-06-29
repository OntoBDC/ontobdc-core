
import os
import sys
import subprocess
from typing import Optional, List
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.shared.domain.port.logger import LoggerAwarePort
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.adapter.terminal import log, prompt_choice, prompt_raw_text
from ontobdc.shared.domain.port.context import PromptChoiceAwarePort, PromptRawTextAwarePort
from ontobdc.shared.domain.resource.logger import LogLevel, LogStrategyResource, NullLogRepository
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse, HelpCommandResponse


def main() -> None:
    """
    Main entry point for the ontobdc CLI.
    
    Parses command line arguments and dispatches to the appropriate handler.
    """
    # cmd: Optional[str] = None
    # config_adapter: ConfigDataPort = ConfigDataAdapter()
    incoming_args: List[str] = [arg for arg in sys.argv[1:] if arg not in ["--json", "--rich", "--silent", "-s"]]

    # Extract the primary command from the command line arguments
    # if len(incoming_args):
    #     cmd = incoming_args[0]

    try:
        render_type: str = 'json' if "--json" in sys.argv else 'rich'
        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        cli_command_run: CliCommandPort = CliCommandRunAdapter.make(incoming_args)

        if _check_command(cli_command_run, incoming_args):
            if isinstance(cli_command_run, LoggerAwarePort):
                log_strategy = LogStrategyResource(
                    print_log=log,
                    log_level=LogLevel.INFORMATIONAL,
                    log_repository=NullLogRepository(),
                )
                cli_command_run.set_log_strategy(log_strategy)

            if isinstance(cli_command_run, PromptChoiceAwarePort):
                cli_command_run.set_prompt_choice(prompt_choice)

            if isinstance(cli_command_run, PromptRawTextAwarePort):
                cli_command_run.set_prompt_raw_text(prompt_raw_text)

            response: CommandResponse = cli_command_run.run()
            if not silent:
                _render_response(response, render_type)

            sys.exit(0)

    except CliCommandArgumentException as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        if len(sys.argv) > 1 and sys.argv[1] not in ["init", "dev"]:
            response = ExceptionCommandResponse(
                title=str(e).split(":")[0].strip(),
                description=f"{str(e)}",
                content={
                    "execution_response": str(e),
                },
            )
            _render_response(response, render_type)
            sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        sys.exit(1)


def _render_response(response: CommandResponse, render_type: str) -> None:
    """
    Render a command response to the console.
    
    Args:
        response: The command response object to render
        render_type: The type of rendering to perform (e.g., 'json' or 'rich')
    """
    if isinstance(response, HelpCommandResponse):
        print(response)
    else:
        print(response)


def _check_command(cli_command_run: CliCommandPort, incoming_args: List[str]) -> bool:
    """
    Check if a command is valid and ready to execute.
    
    Args:
        cli_command_run: The CLI command runner instance
        incoming_args: The command line arguments
    
    Returns:
        True if the command is valid, False otherwise
    
    Note: Most validation is already performed by CliCommandRunAdapter.make()
    """
    return True
    

