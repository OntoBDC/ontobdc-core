from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar

from ontobdc.cli.domain.response.command import CommandResponse


class AnnotationViewSaveProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the saving of the view of an annotation.
    """


class AnnotationViewSaveRequestPort:
    """
    Canonical context keys of the saving of the view of an annotation: the annotation, and the picture of the document it
    is made on as the person left it (a model in space, seen from where they chose), as the text of its bytes.
    """

    GUID_KEY: ClassVar[str] = "annotation_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    VIEW_KEY: ClassVar[str] = "annotation_view"
    PATH_KEY: ClassVar[str] = "annotation_view_path"


class AnnotationViewSaveStateTransitionHandlerPort(ABC):
    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Keep the picture as the view of the annotation.
        """
        ...
