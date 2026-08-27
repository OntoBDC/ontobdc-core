from typing import List

from ontobdc.a3.domain.model.language import A3SupportedLanguages
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class A3BaseCommand(CliCommandPort):
    """Base command for the a3 component.

    Only ``--lang`` is implemented so far: it lists the languages a3
    currently recognizes, the same list ``run``'s intent-resolution
    statechart checks against at its ``language_defined`` state.
    """

    METADATA = CliCommandMetadata(
        id="base",
        logical_component="a3",
        description="List the languages the a3 assistant recognizes.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--lang"],
                "valued": False,
                "description": "List the languages a3 currently recognizes.",
                "usage": "ontobdc a3 --lang",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) >= 1
            and args[0] == "a3"
            and (len(args) == 1 or args[1] == "--lang")
        )

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        return not command_args or command_args == ["--lang"]

    def run(self) -> CommandResponse:
        supported_languages: List[str] = A3SupportedLanguages.list()
        return CommandResponse(
            title="OntoBDC A3",
            description="Languages a3 currently recognizes.",
            content={"supported_languages": supported_languages},
        )
