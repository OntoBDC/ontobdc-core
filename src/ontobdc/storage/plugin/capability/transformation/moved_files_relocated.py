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


class MovedFilesRelocatedCapability(TransactionCapability):
    """
    Identify, by the SHA-256 of its content, the files on disk that the history of the container has
    seen before. The history of every file the container has had is looked at, whether the crate
    states the file now or not: a file that moved (or was renamed) is the file that held that
    content, wherever it is; a copy is the same file, at one more path. Its history gets an entry
    with where it is now. A node a refresh made for the path is the file's node from then on, or
    gives way to it. When several files held the content, the one of the same name is taken; when
    that does not say, the file is left as it is and listed as ambiguous.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "moved_files_relocated"
        ),
        version="2.0.0",
        name="Moved Files Relocated",
        description="Identify, by the SHA-256 of its content, the files on disk that the history of the container has seen before.",
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
        files: ContainerFileRepository = ContainerFileRepository(container_path)
        ledger: FileLedger = FileLedger(document, files)

        sizes = ledger.sizes()
        relocated: List[Dict[str, str]] = []
        ambiguous: List[Dict[str, Any]] = []
        for path in ledger.targets():
            size = files.size(path)
            # The content is read only when a file the history knew could have it.
            if size is None or (None not in sizes and size not in sizes):
                continue
            owner = ledger.owners.get(path)
            sha256: str = files.sha256(path)
            found: List[str] = ledger.by_content(path, sha256, owner)
            if len(found) > 1:
                named: List[str] = ledger.named(found, Path(path).name)
                if len(named) != 1:
                    ambiguous.append({"path": path, "files": sorted(found)})
                    continue
                found = named
            if not found or not ledger.can_take(found[0], owner):
                continue
            entry = files.entry(path, sha256)
            if entry is not None:
                relocated.append(ledger.take(path, found[0], entry, owner))

        if relocated:
            CrateFileHistory.write_document(crate_file, ledger.document)
            ledger.publish_lists(context)
        context.set_parameter_value(Request.RELOCATED_KEY, relocated)

        return {"relocated": relocated, "ambiguous": ambiguous}
