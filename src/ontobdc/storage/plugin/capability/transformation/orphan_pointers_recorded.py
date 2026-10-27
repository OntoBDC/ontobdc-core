from pathlib import Path
from typing import Any, Dict, List, Set

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.adapter.file_ledger import FileLedger
from ontobdc.storage.domain.model.file_history import FileHistory
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class OrphanPointersRecordedCapability(TransactionCapability):
    """
    Say in the history of each file that it is no longer where it was: every path its history says it
    is at and that is not on disk gets an entry that ends it, with what the file was there, so the
    path can be pointed again when the file turns up. A file that is at none of its paths is an orphan
    pointer: the crate still names it, and it is listed.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "orphan_pointers_recorded"
        ),
        version="1.0.0",
        name="Orphan Pointers Recorded",
        description="End in the history of each file the paths it is no longer at, and list the files that are nowhere.",
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
        ledger: FileLedger = FileLedger(document, ContainerFileRepository(container_path))
        own: Dict[str, FileHistory] = CrateFileHistory.node_histories(document)

        when: str = CrateFileHistory.now()
        ended: int = 0
        orphans: List[Dict[str, str]] = []
        for file_id, absent in ledger.orphan_paths().items():
            history: FileHistory = ledger.histories[file_id]
            if absent:
                present: Set[str] = set(history.live_paths()) - absent
                after: FileHistory = CrateFileHistory.end_missing(history, present, when)
                ended += len(absent)
                CrateFileHistory.set_node_history(
                    document, file_id,
                    own[file_id].with_entries([entry for entry in after if entry not in history.entries]),
                )
                history = after
            if history.is_orphan():
                last = history.latest()
                orphans.append({"id": file_id, "path": last.relative_path if last is not None else ""})

        if ended > 0:
            CrateFileHistory.write_document(crate_file, document)
            ledger.publish_lists(context)

        return {"orphans": sorted(orphans, key=lambda item: item["path"]), "paths_ended": ended}
