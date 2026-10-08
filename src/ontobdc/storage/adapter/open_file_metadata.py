import json
from typing import Any, Optional
from pathlib import Path

from ontobdc.shared.adapter.etl import EtlDirectoryContract, EtlEventPayloadKeys
from ontobdc.storage.adapter.taxonomy import OpenFileMetadataTaxonomy
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class OpenFileMetadataEvent:
    """Read the extraction event without depending on its producing capability."""

    @staticmethod
    def container_of(file_path: Path) -> Path:
        """The container that holds the file: where its ETL events live."""
        return ContainerDocumentIri.container_of(file_path)

    @staticmethod
    def path(container_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / OpenFileMetadataTaxonomy.MODULE_NAME
            / OpenFileMetadataTaxonomy.PHASE_NAME
            / OpenFileMetadataTaxonomy.ENTITY_NAME
            / OpenFileMetadataTaxonomy.EVENT_FILE_NAME
        )

    @classmethod
    def mime_for(cls, container_path: Path, file_path: Path) -> Optional[str]:
        event_path: Path = cls.path(container_path)
        event: Any = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise ValueError(f"File metadata ETL event must be an object: {event_path}")
        if event["state"] != OpenFileMetadataTaxonomy.STATE_NAME:
            raise ValueError(f"Invalid file metadata ETL state: {event_path}")
        if event[OpenFileMetadataTaxonomy.RESOLVED_PATH_KEY] != str(
            file_path.expanduser().resolve()
        ):
            raise ValueError(f"File metadata ETL event belongs to another file: {event_path}")
        mime: Any = event[EtlEventPayloadKeys.MIME]
        if mime is not None and (not isinstance(mime, str) or not mime.strip()):
            raise ValueError(f"Invalid MIME in file metadata ETL event: {event_path}")
        return mime
