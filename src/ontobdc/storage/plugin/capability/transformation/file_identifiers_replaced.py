from pathlib import Path
from typing import Any, Dict, List, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class FileIdentifiersReplacedCapability(TransactionCapability):
    """
    Name each file of the RO-Crate by an identifier (a UUID) in place of its path: in its node, and in
    the parts of the root dataset. What the file is called stays in its history, where its latest
    entry says the path. A file already named by an identifier keeps it, and a file whose node has no
    history is left named by its path, because replacing the id would lose where it is.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "file_identifiers_replaced"
        ),
        version="1.0.0",
        name="File Identifiers Replaced",
        description="Name each file of the RO-Crate by a UUID in place of its path.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "reconciliation", "crate", "identity"],
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
        given: Dict[str, str]
        left: List[str]
        given, left = CrateFileHistory.replace_identifiers(document)
        if given:
            CrateFileHistory.write_document(crate_file, document)

        return {"identifiers_given": len(given), "without_history": left}
