from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort
from ontobdc.storage.plugin.machine.open_file.port import OpenFileRequestPort


class AnnotationCreationFromPointProcessStatePort(str, Enum):
    """
    Base enum contract for the annotation creation from point states.
    """


class AnnotationCreationFromPointStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> AnnotationCreationFromPointProcessStatePort:
        """
        Return the annotation creation from point state already reached.
        """
        ...


class AnnotationCreationFromPointStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> AnnotationCreationFromPointProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> AnnotationCreationFromPointProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: AnnotationCreationFromPointProcessStatePort,
        to_state: AnnotationCreationFromPointProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the annotation creation from point machine and return the
        result of its last capability.
        """
        ...


class DrawableDocumentRequestPort(OpenFileRequestPort):
    """
    Canonical context keys consumed by the loading of drawable documents.

    The request is about the same file the open-file keys name (its path and
    its MIME type); only the capability a MIME type is mapped to is a key of
    its own.
    """

    CAPABILITY_BY_MIME_KEY: ClassVar[str] = "drawable_document_capability"


class DrawableDocumentChainSupport(
    DrawableDocumentRequestPort,
    ChainResponsibilityPort,
):
    """
    Responsibility contract for the drawable documents chain.

    A capability that loads the drawable documents of some kind of file
    implements this contract (``can_handle`` says whether it loads the file
    of the request) and is declared as one region of
    ``standard_drawable_documents_chain.yaml``.
    """


class DrawableFileViewerRequestPort(OpenFileRequestPort):
    """
    Canonical context keys consumed by the opening of the viewer of a
    drawable file.

    The request is about the same file the open-file keys name (its path and
    its MIME type); only the capability a MIME type is mapped to is a key of
    its own.
    """

    CAPABILITY_BY_MIME_KEY: ClassVar[str] = "drawable_file_viewer_capability"


class DrawableFileViewerChainSupport(
    DrawableFileViewerRequestPort,
    ChainResponsibilityPort,
):
    """
    Responsibility contract for the drawable file viewer chain.

    A capability that opens the viewer of some kind of file implements this
    contract (``can_handle`` says whether it opens the file of the request)
    and is declared as one region of
    ``standard_drawable_file_viewer_chain.yaml``.
    """


class PointsCapturedRequestPort(OpenFileRequestPort):
    """
    Canonical context keys consumed by the capture of the points of a
    drawable file.

    The request is about the same file the open-file keys name (its path and
    its MIME type); only the capability a MIME type is mapped to is a key of
    its own.
    """

    CAPABILITY_BY_MIME_KEY: ClassVar[str] = "points_captured_capability"


class PointsCapturedChainSupport(
    PointsCapturedRequestPort,
    ChainResponsibilityPort,
):
    """
    Responsibility contract for the points captured chain.

    A capability that captures the points of some kind of file implements this
    contract (``can_handle`` says whether it captures the file of the request)
    and is declared as one region of
    ``standard_points_captured_chain.yaml``.
    """


class AnnotationDetailsRequestPort(OpenFileRequestPort):
    """
    Canonical context keys of the details of the annotations: the ones the
    capability that asks for them leaves, and the one that maps a MIME type
    to that capability.
    """

    CAPABILITY_BY_MIME_KEY: ClassVar[str] = "annotation_details_capability"
    TITLE_KEY: ClassVar[str] = "annotation_title"
    TEXT_KEY: ClassVar[str] = "annotation_text"
    AUTHOR_KEY: ClassVar[str] = "annotation_author"


class AnnotationDetailsChainSupport(
    AnnotationDetailsRequestPort,
    ChainResponsibilityPort,
):
    """
    Responsibility contract for the annotation details chain.

    A capability that asks the person for the details of an annotation made
    on some kind of file implements this contract (``can_handle`` says
    whether it does for the file of the request), leaves them in the context
    under the keys above, and is declared as one region of
    ``standard_annotation_details_chain.yaml``.
    """
