from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.adapter.entity_geometry import EntityGeometries
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.adapter.types import AnnotationTypes
from ontobdc.annotate.domain.model.annotate import Annotation


class AnnotationListCommand(CliCommandPort):
    """
    List the annotations of a container, grouped by annotation type.

    The groups are the annotation types the Brasidatacenter ontology
    declares, each with its labels by language, whether it has annotations or
    not. The annotations come from the data source of the container's
    annotation dataset, read through the entity repository the context
    carries; OntoBDC has no default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_list",
        logical_component="annotate",
        description="List the annotations of a container, grouped by type.",
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container whose annotations are listed, by "
                    "storage identifier. When omitted, the container is "
                    "resolved from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--list"],
                "description": (
                    "List the annotations of the container, grouped by the "
                    "annotation types the ontology declares."
                ),
                "usage": "ontobdc annotation --list [--container <id>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    LIST_FLAG: ClassVar[str] = "--list"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    ITEM_FIELDS: ClassVar[List[str]] = [
        "global_id",
        "title",
        "text",
        "author",
        "created_at",
        "completed_at",
    ]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation list at the CLI routing stage.
        """
        if not args or args[0] != AnnotationListCommand.COMPONENT:
            return False

        return AnnotationListCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        ContainerEntityRepository.provide(context)
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        by_type: Dict[str, List[Dict[str, str]]] = self._annotations_by_type(
            repository, container_path
        )
        groups: List[Dict[str, Any]] = [
            {
                "id": declared["identifier"],
                "iri": declared["iri"],
                "labels": declared["labels"],
                "annotations": by_type.get(declared["identifier"], []),
            }
            for declared in AnnotationTypes.all()
        ]
        count: int = sum(len(group["annotations"]) for group in groups)
        return CommandResponse(
            title="Annotations",
            description=f"{count} annotations in {len(groups)} groups.",
            content={"groups": groups},
        )

    def _annotations_by_type(
        self,
        repository: EntityRepositoryPort,
        container_path: Path,
    ) -> Dict[str, List[Dict[str, str]]]:
        dataset_path: Optional[Path] = EntityDatasets.first(
            container_path, Annotation.ENTITY_IRI
        )
        if dataset_path is None or not repository.data_source_exists(dataset_path):
            return {}

        by_type: Dict[str, List[Dict[str, str]]] = {}
        row: Dict[str, str]
        for row in repository.rows(dataset_path).values():
            by_type.setdefault(row.get("annotation_type", ""), []).append(
                self._item(row, container_path, dataset_path)
            )

        return by_type

    def _item(self, row: Dict[str, str], container_path: Path, dataset_path: Path) -> Dict[str, Any]:
        """
        What the listing says of one annotation: its fields as the row holds
        them, and the files it is made on and refers to as paths in the
        container, which is what a person opens (the row keeps their IRIs). Its geometries are told by
        their kind and number of dimensions: what they are made of is what ``--inspect`` of the entity says.
        """
        item: Dict[str, Any] = {field: row.get(field, "") for field in self.ITEM_FIELDS}
        item["geometry"] = [
            {"type": kind, "dimension": dimension, "shape": shape}
            for kind, dimension, shape in (
                (*EntityGeometries.describe(geometry.wkt), geometry.shape)
                for geometry in EntityGeometries.read(dataset_path, row.get("global_id", ""))
            )
        ]
        item["source_document"] = self._path(row.get("source_document", ""), container_path)
        item["related_documents"] = [
            path
            for path in (
                self._path(iri, container_path)
                for iri in row.get("related_documents", "").split(Annotation.RELATED_SEPARATOR)
            )
            if path
        ]
        return item

    @staticmethod
    def _path(iri: str, container_path: Path) -> str:
        return ContainerDocumentIri.path_of(container_path, iri) or "" if iri else ""

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --list, optionally followed by
        --container and its value.
        """
        if scoped_args == [AnnotationListCommand.LIST_FLAG]:
            return True

        return (
            len(scoped_args) == 3
            and AnnotationListCommand.LIST_FLAG in scoped_args
            and AnnotationListCommand.CONTAINER_FLAG in scoped_args
            and AnnotationListCommand._value_after(
                scoped_args, AnnotationListCommand.CONTAINER_FLAG
            )
            not in (None, AnnotationListCommand.LIST_FLAG)
        )

    @staticmethod
    def _value_after(args: List[str], flag: str) -> Optional[str]:
        index: int = args.index(flag)
        if index + 1 >= len(args):
            return None

        value: str = args[index + 1].strip()
        return value if value and not value.startswith("--") else None
