from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import FileHistory
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class CurrentStateRecordedCapability(TransactionCapability):
    """
    Add to the history of each file the RO-Crate states an entry with what the file is now: its
    path, the hash of its content and its timestamp. The history is a property of the node of the
    file, so it is kept for the files the crate states that are on disk; a file of the same name
    found elsewhere has no node, and is not recorded. An entry the history already has is not added
    again, and nothing the history had is taken out.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "current_state_recorded"
        ),
        version="1.0.0",
        name="Current State Recorded",
        description="Add to the history of each file in the RO-Crate an entry with its current state.",
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
        existing: List[str] = list(context.get_parameter_value(Request.EXISTING_KEY) or [])

        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)
        document: Dict[str, Any] = CrateFileHistory.read_document(crate_file)
        files: ContainerFileRepository = ContainerFileRepository(container_path)
        owners: Dict[str, str] = CrateFileHistory.owners(document)
        histories: Dict[str, FileHistory] = CrateFileHistory.node_histories(document)

        # A file at several paths has one history, with the entries of each path.
        recorded: int = 0
        seen: int = 0
        for path in existing:
            owner: Optional[str] = owners.get(path)
            if owner is None:
                continue
            seen += 1
            history: FileHistory = histories[owner]
            histories[owner] = CrateFileHistory.history_of(files, path, history)
            recorded += len(histories[owner]) - len(history)
        if recorded > 0:
            for node_id, history in histories.items():
                CrateFileHistory.set_node_history(document, node_id, history)
            CrateFileHistory.write_document(crate_file, document)

        return {"recorded": recorded, "files_with_history": seen}
