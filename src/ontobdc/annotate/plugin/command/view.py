from typing import Any, ClassVar, List

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.plugin.machine.annotation_view_save.machine import (
    AnnotationViewSaveStateTransitionHandler,
)
from ontobdc.annotate.plugin.machine.annotation_view_save.port import AnnotationViewSaveRequestPort as Request


class AnnotationViewCommand(CliCommandPort):
    """
    Keep the picture of the document an annotation is made on as the person left it: a model in space, seen from where
    they chose, with the shapes they put in it. The annotation is the one whose global id ``--guid`` gives and the
    picture is the PNG whose bytes ``--view`` carries as base64 text. It is kept beside the annotation, in the documents of
    its dataset, named by the global id, in place of the one it had. It is written by the machine that keeps the view of
    an annotation, through the entity repository the context carries; OntoBDC has no default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_view",
        logical_component="annotate",
        description="Keep the picture of the document of an annotation as the person left it, by its global id and the base64 text of the PNG.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": Request.GUID_KEY,
                "description": "Global id of the annotation whose view is kept.",
                "type": "str",
                "usage": "ontobdc annotate --guid <id> --view <base64 of a PNG> [--container <id>]",
            },
            {
                "accepts": ["--view"],
                "valued": True,
                "parameter": Request.VIEW_KEY,
                "description": "The picture, a PNG, as base64 text.",
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": Request.CONTAINER_KEY,
                "description": (
                    "Select the container that keeps the annotation, by storage identifier. When omitted, the "
                    "container is resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--guid", "--view"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--container"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != AnnotationViewCommand.COMPONENT:
            return False

        return AnnotationViewCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        # Before anything is changed for a picture that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)

        return AnnotationViewSaveStateTransitionHandler(context).execute()

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid and --view, optionally --container, each with a value,
        in any order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = AnnotationViewCommand.REQUIRED_FLAGS + AnnotationViewCommand.OPTIONAL_FLAGS
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in AnnotationViewCommand.REQUIRED_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
