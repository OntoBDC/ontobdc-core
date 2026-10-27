from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import DatasetHistoryEntry, without_superseded
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class DatasetHistoryRecordedCapability(TransactionCapability):
    """
    Record the history of every file in the ``fileHistory`` of the root dataset of the RO-Crate too,
    in one list ordered by timestamp, each entry with the identifier of its file besides the path, the
    hash and the timestamp. The entries the root dataset already had stay, so the history of a file
    that is gone is not lost; an entry it already has is not added again.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "dataset_history_recorded"
        ),
        version="1.0.0",
        name="Dataset History Recorded",
        description="Record the history of every file in the fileHistory of the root dataset of the RO-Crate.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "reconciliation", "crate", "history"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, Request.CONTAINER_KEY)
        ).expanduser().resolve()
        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)

        document: Dict[str, Any] = CrateFileHistory.read_document(crate_file)
        before: List[DatasetHistoryEntry] = CrateFileHistory.read_dataset_entries(document)
        entries: List[DatasetHistoryEntry] = without_superseded(CrateFileHistory.dataset_entries_of(document))
        if set(entries) != set(before):
            CrateFileHistory.set_dataset_entries(document, entries)
            CrateFileHistory.write_document(crate_file, document)

        return {"dataset_entries": len(set(entries)), "dataset_entries_added": len(set(entries) - set(before))}
