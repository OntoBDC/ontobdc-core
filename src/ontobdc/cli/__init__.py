from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from ontobdc.cli.adapter.logger import (
    InLineLogger,
    NullLogRepository,
    StandardConsoleLogger,
)
from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.adapter.argument import CliGlobalArgumentParserAdapter
from ontobdc.cli.adapter.renderer import (
    BorderlessTerminalSurfaceAdapter,
    CommandResponseRenderAdapter,
    ResponseWidgetLoaderAdapter,
    TerminalSurfaceAdapter,
)
from ontobdc.shared.adapter.loader import ParameterLoader
from ontobdc.cli.adapter.loader import ExceptionCommandResponseLoader
from ontobdc.cli.domain.port.logger import LogRepositoryPort, LoggerAwarePort
from ontobdc.cli.domain.model.logger import LogLevel, LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.renderer import (
    CommandResponseRendererPort,
    TerminalSurfacePort,
)
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    InteractiveCommandResponse,
)
from ontobdc.shared.facade.adapter.logger import ActiveLogRepositoryBroker

# Set by a caller that pipes this CLI's output somewhere whose real display
# width this process cannot query -- an embedded terminal panel in a
# browser tab, for instance, is neither a TTY nor a fixed 80 columns.
# shutil.get_terminal_size() (used to size the box frame) falls back to a
# guessed 80 columns in that case, and a frame sized for the wrong width
# is far more visibly broken than plain, unframed text ever is, so such a
# caller opts out of the frame entirely rather than risk the mismatch.
BORDERLESS_ENVIRONMENT_VARIABLE: str = "ONTOBDC_CLI_BORDERLESS"


def main() -> None:
    """
    Main entry point for the ontobdc CLI.

    Parses command line arguments and dispatches to the appropriate handler.
    """
    # Strip CLI-owned output flags before command routing. Command matching is
    # positional, so renderer and silence flags must never reach accepts().
    global_argument_parser: CliGlobalArgumentParserAdapter = (
        CliGlobalArgumentParserAdapter()
    )
    incoming_args: List[str] = global_argument_parser.strip_output_flags()

    # Build the response renderer up front so both the success and the error
    # paths render through the same collaborators.
    surface: TerminalSurfacePort = (
        BorderlessTerminalSurfaceAdapter()
        if os.environ.get(BORDERLESS_ENVIRONMENT_VARIABLE) == "1"
        else TerminalSurfaceAdapter()
    )
    response_renderer: CommandResponseRendererPort = CommandResponseRenderAdapter(
        widget_loader=ResponseWidgetLoaderAdapter(),
        surface=surface,
    )

    # Keep the logger reference outside the try block so the error path can
    # safely reuse it even when initialization fails partway through startup.
    logger: Optional[LogRepositoryPort] = None
    try:
        # Resolve the output renderer requested by the user. Rich terminal
        # output is the default unless JSON or HTML is explicitly requested.
        render_type: str = 'rich'
        if "--json" in sys.argv:
            render_type = 'json'
        elif "--html" in sys.argv:
            render_type = 'html'

        # Silence suppresses the final command response while still allowing
        # the command pipeline itself to execute normally.
        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        # Select the logger implementation that matches the chosen renderer.
        # JSON must remain free of console log noise, while rich output keeps
        # logs inline with the terminal presentation surface.
        logger = StandardConsoleLogger()
        if render_type == 'json':
            logger = NullLogRepository()
        elif render_type == 'rich':
            logger = InLineLogger()

        # Consume the global --log-level option before command routing and
        # retain the sanitized argument vector used to resolve the command.
        resolved_log_level: Optional[LogLevel]
        sanitized_incoming_args: List[str]
        resolved_log_level, sanitized_incoming_args = (
            global_argument_parser.consume_log_level(incoming_args)
        )

        # Apply an explicit threshold before exposing the logger through the
        # global broker. When --log-level is omitted, the repository keeps
        # LogLevelPolicy.DEFAULT (NOTICE).
        if resolved_log_level is not None:
            _ = LogStrategyConfig(
                log_level=resolved_log_level,
                log_repository=logger,
            )

        # Publish the selected logger through the process-wide broker so
        # lower layers can resolve the same active repository during the run.
        ActiveLogRepositoryBroker.instance().set(logger)

        # Resolve the concrete command from the sanitized arguments. Validation
        # is deliberately deferred because parameter binding happens below.
        cli_command_run: CliCommandPort = CliCommandRunAdapter.make(
            sanitized_incoming_args,
            logger,
            defer_check=True,
        )

        if cli_command_run.METADATA.interactive and render_type != "rich":
            raise CliCommandArgumentException(
                f"Interactive command '{cli_command_run.METADATA.id}' "
                f"does not support {render_type} output."
            )

        # Propagate an explicit global log level into the command context so
        # command-level parameter consumers see the same resolved value.
        if resolved_log_level is not None:
            request: Optional[Any] = getattr(cli_command_run, "_request", None)
            context: Optional[CliContextPort] = getattr(request, "context", None)
            if context is not None:
                context.set_parameter_value("log_level", resolved_log_level)

        # Bind explicit and implicit parameters, then execute only when the
        # command-specific validation stage accepts the resulting context.
        parameter_validator: CliParameterValidationOrchestrator = (
            CliParameterValidationOrchestrator()
        )
        if parameter_validator.check(
            cli_command_run,
            sanitized_incoming_args,
            logger,
        ):
            # Commands that are logger-aware receive a runtime log strategy
            # backed by the same repository selected for this invocation.
            if isinstance(cli_command_run, LoggerAwarePort):
                log_strategy_kwargs: Dict[str, Any] = {"log_repository": logger}
                if resolved_log_level is not None:
                    log_strategy_kwargs["log_level"] = resolved_log_level
                log_strategy = LogStrategyConfig(**log_strategy_kwargs)
                cli_command_run.set_log_strategy(log_strategy)

            # Execute the resolved command after every dependency and parameter
            # required by the command has been configured.
            response: CommandResponse = cli_command_run.run()

            # Render ordinary responses unless --silent was requested.
            # Interactive responses own their terminal interaction and therefore
            # must not be rendered a second time by the outer CLI shell.
            if not silent and not isinstance(
                response,
                InteractiveCommandResponse,
            ):
                response_renderer.render(response, render_type)

            # A fully validated and executed command terminates successfully.
            sys.exit(0)

    except Exception as e:
        # Recover the renderer defensively in case the failure happened before
        # render_type was initialized inside the try block.
        try:
            safe_render_type: str = render_type
        except NameError:
            safe_render_type = "rich"

        # Recover the silence flag for the same early-startup failure scenario.
        try:
            safe_silent: bool = silent
        except NameError:
            safe_silent = False

        # Convert every uncaught CLI failure into the standard command-response
        # model so all renderer modes share the same error presentation path.
        loader: ExceptionCommandResponseLoader = ExceptionCommandResponseLoader(e)
        response: CommandResponse = loader.get()

        # Respect --silent for failures as well; otherwise render the normalized
        # exception response using the safest available renderer and logger.
        if not safe_silent:
            response_renderer.render(response, safe_render_type)

        # Any uncaught exception represents a failed CLI invocation.
        sys.exit(1)
    finally:
        # Always clear process-wide logger state so one invocation cannot leak
        # its active repository into a subsequent command run.
        ActiveLogRepositoryBroker.instance().clear()


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

            self.configure_parameter_strategy(
                parameter_strategy,
                logger,
                parameter_loader.root_packages,
            )
            parameter_strategy.execute(context)

        if not cli_command_run.check():
            raise CliCommandArgumentException(
                f"Invalid command arguments: {incoming_args}",
                command_args=incoming_args,
            )

        return True

    def apply_explicit_parameter_values(
        self,
        cli_command_run: CliCommandPort,
        incoming_args: List[str],
        context: CliContextPort,
    ) -> None:
        """Copy every valued long-flag (``--foo value``) declared by the
        command's ``METADATA`` into ``context``. The optional ``parameter``
        metadata entry owns the context key; otherwise the flag's snake_case
        name is used.

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

                parameter_name: str = str(
                    argument_definition.get("parameter")
                    or accepted_flag[2:].replace("-", "_")
                )
                context.set_parameter_value(
                    parameter_name,
                    incoming_args[next_index],
                )
                break

    def resolve_required_parameter_names(
        self,
        cli_command_run: CliCommandPort,
    ) -> Set[str]:
        """Return the parameter keys the command's ``METADATA`` declares.

        Parameter strategies whose ``METADATA.name`` is not in this set are
        skipped during the implicit stage, which keeps the parameter
        pipeline deterministic and avoids leaking shared strategies into
        commands that never asked for them. An explicit ``parameter`` entry
        takes precedence over the long flag's derived snake_case name.
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

            explicit_parameter_name: Any = argument_definition.get("parameter")
            if (
                isinstance(explicit_parameter_name, str)
                and explicit_parameter_name.strip()
            ):
                required_parameter_names.add(explicit_parameter_name.strip())
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
        root_packages: Tuple[str, ...],
    ) -> None:
        """Attach to a parameter strategy what it declares support for:
        the logger via the ``LoggerAwarePort`` marker port, and the
        packages plugins are discovered in via ``RootPackagesAwarePort``.

        A strategy that loads plugins of its own gets the same scope the
        parameter loader was given, which is the executable's own: an
        executable reusing this runtime registers plugins under its own
        package, and a strategy searching only this one would never find
        them.
        """
        if isinstance(parameter_strategy, LoggerAwarePort):
            parameter_strategy.set_log_strategy(
                LogStrategyConfig(
                    log_repository=logger,
                )
            )

        if isinstance(parameter_strategy, RootPackagesAwarePort):
            parameter_strategy.set_root_packages(root_packages)
