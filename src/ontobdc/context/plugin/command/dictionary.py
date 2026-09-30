from typing import ClassVar, List, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from ontobdc.context.plugin.machine.dictionary_inspection.machine import (
    DictionaryInspectionStateTransitionHandler,
)


class ContextDictionaryInspectCommand(CliCommandPort):
    """Inspect an arbitrary value through the context dictionary FSM."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="context_dictionary_inspect",
        logical_component="context",
        description="Inspect a value in the context dictionary.",
        arguments=[
            {
                "accepts": ["--term"],
                "valued": True,
                "parameter": "text",
                "description": "Term or value to inspect in the context dictionary.",
            },
            {
                "accepts": ["--inspect"],
                "description": "Run the context dictionary inspection pipeline.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "context"
    TERM_FLAG: ClassVar[str] = "--term"
    INSPECT_FLAG: ClassVar[str] = "--inspect"
    TEXT_CONTEXT_KEY: ClassVar[str] = "text"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContextDictionaryInspectCommand.COMPONENT:
            return False
        return ContextDictionaryInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        term_value: Optional[str] = self._extract_term(
            self._request.command_args
        )
        if term_value is None:
            return False
        self._request.context.set_parameter_value(
            self.TEXT_CONTEXT_KEY, term_value
        )
        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        return (
            ContextDictionaryInspectCommand._extract_term(scoped_args)
            is not None
        )

    @staticmethod
    def _extract_term(scoped_args: List[str]) -> Optional[str]:
        if ContextDictionaryInspectCommand.INSPECT_FLAG not in scoped_args:
            return None

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContextDictionaryInspectCommand.INSPECT_FLAG)

        term_value: Optional[str] = (
            ContextDictionaryInspectCommand._extract_valued_flag(
                remaining, ContextDictionaryInspectCommand.TERM_FLAG
            )
        )
        if term_value is None or remaining:
            return None

        return term_value

    @staticmethod
    def _extract_valued_flag(
        remaining: List[str], flag: str
    ) -> Optional[str]:
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip():
            return None

        del remaining[index:index + 2]
        return value.strip()

    def run(self) -> CommandResponse:
        return DictionaryInspectionStateTransitionHandler(
            context=self._request.context
        ).execute()
