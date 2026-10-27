from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.adapter.file_ledger import FileLedger
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class SameNameAndSizeFilesRelocatedCapability(TransactionCapability):
    """
    Identify, by their name and size, the files on disk the content could not identify: the history of
    the container is looked at for the files that had that name and that size, and a file on disk is
    taken for one when it is the only candidate and no other file on disk is a candidate for it too.
    The content may have changed (what the content-based state cannot follow), so the entry carries
    the hash the file has now. Only files that are nowhere now are candidates: a file that is
    still there with that name and size is another file.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "same_name_and_size_files_relocated"
        ),
        version="2.0.0",
        name="Same Name And Size Files Relocated",
        description="Identify, by their name and size, the files on disk that the history of the container has seen before, when there is a single candidate.",
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
        relocated_before: List[Dict[str, str]] = list(context.get_parameter_value(Request.RELOCATED_KEY) or [])

        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)
        document: Dict[str, Any] = CrateFileHistory.read_document(crate_file)
        files: ContainerFileRepository = ContainerFileRepository(container_path)
        ledger: FileLedger = FileLedger(document, files)

        proposals: Dict[str, str] = {}
        for path in ledger.targets():
            size = files.size(path)
            if size is None:
                continue
            owner = ledger.owners.get(path)
            found: List[str] = [
                file_id for file_id in ledger.by_name_and_size(Path(path).name, size, owner)
                if not ledger.is_alive(file_id)
            ]
            if len(found) == 1:
                proposals[path] = found[0]

        claims: Dict[str, int] = {}
        for file_id in proposals.values():
            claims[file_id] = claims.get(file_id, 0) + 1

        relocated: List[Dict[str, str]] = []
        for path, file_id in proposals.items():
            owner = ledger.owners.get(path)
            if claims[file_id] != 1 or not ledger.can_take(file_id, owner):
                continue
            entry = files.entry(path)
            if entry is not None:
                relocated.append(ledger.take(path, file_id, entry, owner))

        if relocated:
            CrateFileHistory.write_document(crate_file, ledger.document)
            ledger.publish_lists(context)
            context.set_parameter_value(Request.RELOCATED_KEY, [*relocated_before, *relocated])

        return {"relocated_by_name_and_size": relocated}
