
from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass, field
from ontobdc.cli.init import log as print_log
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.context import CliContextAdapter
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.domain.port.context import CliContextPort


@dataclass
class CliCommandRequest:
    """
    Normalized representation of a CLI command request.
    """
    logical_component: Optional[str] = None
    component_action: Optional[str] = None
    command_args: List[str] = field(default_factory=list)
    context: CliContextPort = field(default_factory=CliContextPort)


class CliCommandRunAdapter:
    """
    Small adapter layer for future command-style CLI execution.

    The current `ontobdc.cli.__init__.py` still contains the legacy dispatch
    flow, so this adapter must be safe to call before that logic runs.
    """
    @classmethod
    def make(cls, args: List[str]) -> CliCommandPort:
        """
        Create a command adapter from raw CLI arguments.
        """
        if len(args) == 0 or args[0] in ["--help", "-h"]:
            loader: PluginResource = CommandLoader('cli', print_log)
            command_class: Optional[type[CliCommandPort]] = loader.get('command', 'base')
            if isinstance(command_class, type):
                return command_class(
                    CliCommandRequest(
                        logical_component="cli",
                        component_action="base",
                        command_args=args,
                        context=CliContextAdapter(args),
                    )
                )

        elif isinstance(args[0], str):
            logical_component: str = args[0]
            args.remove(logical_component)
            loader: PluginResource = CommandLoader(logical_component, print_log)

            if len(args) == 0:
                for command_class in loader.get_all():
                    if not isinstance(command_class, type):
                        continue

                    if len(command_class.METADATA.arguments[0]["accepts"]):
                        continue

                    req = CliCommandRequest(
                        logical_component=logical_component,
                        component_action=command_class.METADATA.id,
                        command_args=args,
                        context=CliContextAdapter(args),
                    )
                    cmd_instance = command_class(req)
                    if cmd_instance.check():
                        return cmd_instance

                args.append("--help")

            for command_class in loader.get_all():

                if not isinstance(command_class, type):
                    continue

                matched_argument: Optional[dict] = None
                for argument in command_class.METADATA.arguments:
                    accepted_args: List[str] = argument.get("accepts", [])
                    if args[0] in accepted_args:
                        matched_argument = argument
                        break

                if matched_argument is None:
                    continue

                expected_args_len = 0
                for argument in command_class.METADATA.arguments:
                    expected_args_len += 2 if argument.get("valued") else 1

                if expected_args_len > len(args):
                    continue

                req = CliCommandRequest(
                    logical_component=logical_component,
                    component_action="base",
                    command_args=args,
                    context=CliContextAdapter(args),
                )

                cmd_instance = command_class(req)
                if cmd_instance.check():
                    return cmd_instance

        raise CliCommandArgumentException(f"Invalid command arguments: {args}")
