from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationRequestPort as Request,
)


class MissingFilesListedCapability(TransactionCapability):
    """
    List the files the RO-Crate of the container states that are not on disk. The crate is what the
    container says it holds; the disk is what it holds. A directory the crate states is not a file,
    and is left out.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "missing_files_listed"
        ),
        version="1.0.0",
        name="Missing Files Listed",
        description="List the files the RO-Crate of the container states that are not on disk.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "reconciliation", "crate"],
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

        files: ContainerFileRepository = ContainerFileRepository(container_path)
        stated: List[str] = [
            path for path in ContainerRoCrate.file_paths(container_path) if not path.endswith("/")
        ]
        missing: List[str] = [
            path for path in stated if not files.is_file(path)
        ]
        context.set_parameter_value(Request.MISSING_KEY, missing)
        context.set_parameter_value(
            Request.EXISTING_KEY, [path for path in stated if path not in set(missing)]
        )
        return {"stated": len(stated), "missing": missing}
