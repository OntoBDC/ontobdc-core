import re
from typing import Any, ClassVar, Dict, List, Tuple, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import RunCommandResponse
from ontobdc.run.adapter.fsm import FsmHandlerLocator


class RunFsmCommand(CliCommandPort):
    """
    Run a finite state machine from the YAML of its statechart.

    ``run --fsm <yaml>`` finds the handler of the machine by the layout of the
    folder the YAML is in (see ``FsmHandlerLocator``) and has it run the
    machine, state by state, as the machine itself defines: whatever each
    state leaves behind is the machine's own business. What the machine
    needs from its caller is given as flags named after its parameters:
    ``--annotation-type issue`` sets the parameter ``annotation_type``. The
    container it works on is the one ``--container`` selects, or the one the
    current directory resolves to.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="fsm",
        logical_component="run",
        description="Run a finite state machine from the YAML of its statechart.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--fsm"],
                "valued": True,
                "parameter": "fsm_path",
                "description": (
                    "Path of the statechart YAML of the machine to run, or its "
                    "path inside an installed package."
                ),
                "type": "Path",
                "usage": (
                    "ontobdc run --fsm <yaml> [--container <id>] "
                    "[--<parameter-name> <value>]..."
                ),
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container the machine works on, by storage "
                    "identifier. When omitted, the container is resolved from "
                    "the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "run"
    FSM_FLAG: ClassVar[str] = "--fsm"
    CAPABILITY_FLAG: ClassVar[str] = "--capability"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    FSM_KEY: ClassVar[str] = "fsm_path"
    FLAG: ClassVar["re.Pattern[str]"] = re.compile(r"--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
    # Flags the command itself binds; the rest are the machine's parameters.
    BOUND_FLAGS: ClassVar[Tuple[str, ...]] = ("--fsm", "--container")

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the run of a machine at the CLI routing stage.
        """
        if not args or args[0] != RunFsmCommand.COMPONENT:
            return False

        return RunFsmCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> RunCommandResponse:
        context: Any = self._request.context
        fsm: str = str(context.get_parameter_value(self.FSM_KEY) or "").strip()
        statechart, handler_type = FsmHandlerLocator.locate(fsm)

        for flag, value in self._parameters(self._request.command_args).items():
            context.set_parameter_value(flag, value)

        result: Dict[str, Any] = handler_type(context).execute()
        return RunCommandResponse(
            title="OntoBDC Run",
            description=f"{handler_type.__name__} ran {statechart.name}.",
            content={"fsm": str(statechart), "result": result},
        )

    @classmethod
    def _parameters(cls, scoped_args: List[str]) -> Dict[str, str]:
        """
        The machine's parameters among the arguments: each flag but the ones
        the command binds, named with underscores, with its value.
        """
        return {
            flag[2:].replace("-", "_"): value
            for flag, value in zip(scoped_args[0::2], scoped_args[1::2])
            if flag not in cls.BOUND_FLAGS
        }

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --fsm with its value, then any
        number of flags each with a value, none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        if RunFsmCommand.FSM_FLAG not in flags:
            return False
        if RunFsmCommand.CAPABILITY_FLAG in flags:
            return False
        if len(set(flags)) != len(flags):
            return False
        if any(not RunFsmCommand.FLAG.fullmatch(flag) for flag in flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
