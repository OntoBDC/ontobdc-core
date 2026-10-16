from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar


class AnnotationExportToExcelProcessStatePort(str, Enum):
    """
    Base enum contract for the annotation export to Excel states.
    """


class AnnotationExportToExcelRequestPort:
    """
    What the export reads from the context, by parameter name.
    """

    # Of the request.
    ANNOTATION_TYPE_KEY: ClassVar[str] = "annotation_type"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    LANGUAGE_KEY: ClassVar[str] = "export_language"
    OUTPUT_KEY: ClassVar[str] = "export_output_path"
    # Between the capabilities of a run.
    GROUP_KEY: ClassVar[str] = "export_group"
    ITEMS_KEY: ClassVar[str] = "export_items"
    PHOTOS_KEY: ClassVar[str] = "export_photos"
    WORKBOOK_KEY: ClassVar[str] = "export_workbook_path"


class AnnotationExportToExcelStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> AnnotationExportToExcelProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: AnnotationExportToExcelProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: AnnotationExportToExcelProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: AnnotationExportToExcelProcessStatePort,
        to_state: AnnotationExportToExcelProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: AnnotationExportToExcelProcessStatePort) -> None:
        ...
