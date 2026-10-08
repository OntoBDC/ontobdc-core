import json
import os
import tempfile
from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from ontobdc.annotation.plugin.machine.annotation_creation_from_point.port import (
    AnnotationCreationFromPointProcessStatePort,
)


class AnnotationCreationFromPointEtlEvent:
    """
    The ETL file every state of the annotation creation from point machine
    leaves behind::

        <container>/.__ontobdc__/etl/annotation/creation/point/<state>.json

    The container is the one that holds the file the annotation is made on
    (``container_of``), not the storage root: what a run leaves behind belongs
    with the container whose file it was about.
    It names the state and carries what the state produced, so the
    run can be followed state by state from the files alone.
    """

    ETL_MODULE_NAME: ClassVar[str] = "annotation"
    ETL_PHASE_NAME: ClassVar[str] = "creation"
    ETL_ENTITY_NAME: ClassVar[str] = "point"
    FILE_KEY: ClassVar[str] = "file_open_path"

    @classmethod
    def container_of(cls, context: CliContextPort) -> Path:
        """
        The container the ETL files of a run go to: the one that holds the
        file of the request.

        Raises:
            ValueError: the request names no file.
            LookupError: the file is inside no container.
        """
        return ContainerDocumentIri.container_of(
            Path(RequiredParameter.of(context, cls.FILE_KEY))
        )

    @classmethod
    def path(
        cls,
        container_path: Path,
        state: AnnotationCreationFromPointProcessStatePort,
    ) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / cls.ETL_MODULE_NAME
            / cls.ETL_PHASE_NAME
            / cls.ETL_ENTITY_NAME
            / f"{state.value}.json"
        )

    @classmethod
    def write(
        cls,
        container_path: Path,
        state: AnnotationCreationFromPointProcessStatePort,
        result: Dict[str, Any],
    ) -> Path:
        """
        Write the state's file, replacing the one an earlier run left.

        A live object a capability leaves in the result, such as a loaded
        document or an open window, cannot be persisted: the file names
        its type instead (``"<Drawing>"``).
        """
        target: Path = cls.path(container_path, state)
        cls.write_text(
            target,
            json.dumps(
                {
                    "state": state.value,
                    "phase": cls.ETL_PHASE_NAME,
                    "entity": cls.ETL_ENTITY_NAME,
                    "result": result,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=cls._describe,
            ),
        )
        return target

    @staticmethod
    def _describe(value: Any) -> str:
        return f"<{type(value).__name__}>"

    @staticmethod
    def write_text(target: Path, text: str) -> None:
        """
        Write ``text`` to ``target`` atomically, creating its directory:
        a reader sees the previous file or the whole new one.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path: Path = Path(handle.name)
            handle.write(text + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(target)
