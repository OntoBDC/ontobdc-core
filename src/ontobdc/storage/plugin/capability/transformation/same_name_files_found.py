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


class SameNameFilesFoundCapability(TransactionCapability):
    """
    For each file the crate states and the disk does not have, find the files of the same name that
    are somewhere else in the container. It only identifies: a file of the same name may have been
    moved there, or may be another one. What the container keeps hidden (a directory whose name
    starts with a dot, which holds the container's own metadata) is not looked into.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "same_name_files_found"
        ),
        version="1.0.0",
        name="Same Name Files Found",
        description="Find, for each missing file, the files of the same name elsewhere in the container.",
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
        missing: List[str] = list(context.get_parameter_value(Request.MISSING_KEY) or [])

        by_name: Dict[str, List[str]] = self._files_by_name(ContainerFileRepository(container_path))
        stated: set = set(ContainerRoCrate.file_paths(container_path))

        found: List[Dict[str, Any]] = [
            {
                "path": path,
                "same_name": [
                    {"path": other, "in_crate": other in stated}
                    for other in by_name.get(Path(path).name, [])
                    if other != path
                ],
            }
            for path in missing
        ]
        context.set_parameter_value(Request.FOUND_KEY, found)
        return {
            "missing": found,
            "with_same_name": sum(1 for entry in found if entry["same_name"]),
        }

    @staticmethod
    def _files_by_name(files: ContainerFileRepository) -> Dict[str, List[str]]:
        """The files of the container by their name, each with its path in the container."""
        by_name: Dict[str, List[str]] = {}
        for relative in files.list():
            by_name.setdefault(Path(relative).name, []).append(relative)

        return by_name
