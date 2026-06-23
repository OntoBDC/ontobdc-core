
from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from ontobdc.cli.adapter.terminal import log
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.context import CliContextAdapter
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource
from ontobdc.cli.domain.exception.command import CliCommandArgumentException


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
    def make(cls, args: List[str], print_log: callable = log) -> CliCommandPort:
        """
        Create a command adapter from raw CLI arguments.
        """
        candidate_list: Dict[str, CliCommandPort] = {}

        clean_args: List[str] = args
        loader: PluginResource = CommandLoader('cli', print_log)
        if args:
            if not args[0].startswith("-"):
                loader: PluginResource = CommandLoader(args[0], print_log)
                clean_args = args[1:]

        for command_class in loader.get_all():
            if isinstance(command_class, type):
                if command_class.accepts(args):
                    candidate_list[command_class.METADATA.id] = command_class

        if len(candidate_list) == 0:
            raise CliCommandArgumentException(f"Invalid command arguments: {args}")
        else:
            instance_list: Dict[str, CliCommandPort] = {}
            for uri, command_class in candidate_list.items():
                req = CliCommandRequest(
                    logical_component=command_class.METADATA.logical_component,
                    component_action=command_class.METADATA.id,
                    command_args=clean_args,
                    context=CliContextAdapter(clean_args),
                )
                cmd_instance = command_class(req)
                if cmd_instance.check():
                    instance_list[uri] = cmd_instance

            if len(instance_list) == 0:
                raise CliCommandArgumentException(f"Invalid command arguments: {args}")
            elif len(instance_list) == 1:
                return instance_list[list(instance_list.keys())[0]]
            else:
                print(instance_list)
                raise CliCommandArgumentException(f"Invalid command arguments: {args} - Multiple commands match {args}")    
