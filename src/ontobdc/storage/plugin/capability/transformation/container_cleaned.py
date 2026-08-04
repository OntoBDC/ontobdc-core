from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState
from ontobdc.storage.plugin.check.is_container_cleaned.check import (
    evaluate as evaluate_container_cleaned,
    find_matching_files,
)
from ontobdc.storage.plugin.check.is_container_cleaned.hotfix import (
    main as hotfix_container_cleaned,
)


class ContainerCleanedCapability(TransactionCapability):
    """Remove the configured transient files from a storage container."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_cleaned"
        ),
        version="1.0.0",
        name="Cleaned Container",
        description=(
            "Remove the files configured for cleanup before container "
            "metadata descriptors are synchronized."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "cleanup"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(
        self,
        file_names_to_clean: Optional[Sequence[str]] = None,
    ) -> None:
        self._file_names_to_clean: List[str] = self._normalize_file_names(
            file_names_to_clean
            if file_names_to_clean is not None
            else [".DS_Store", "__pycache__"]
        )

    @property
    def file_names_to_clean(self) -> List[str]:
        return list(self._file_names_to_clean)

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_CLEANED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_CLEANED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        matching_files: List[Path] = find_matching_files(
            container_path=str(container_path),
            file_names=self._file_names_to_clean,
        )
        removed_files: List[str] = [
            file_path.relative_to(container_path).as_posix()
            for file_path in matching_files
        ]

        if matching_files and hotfix_container_cleaned(
            container_path=str(container_path),
            root_path=str(context.root_path),
            file_names=self._file_names_to_clean,
        ) != 0:
            raise ValueError("Could not clean the storage container.")

        if evaluate_container_cleaned(
            container_path=str(container_path),
            file_names=self._file_names_to_clean,
        ) != 0:
            raise ValueError(
                "The storage container is not clean after the cleanup step."
            )

        return {
            "resulting_state": ContainerUpdateProcessState.CONTAINER_CLEANED,
            "container_path": str(container_path),
            "configured_file_names": self.file_names_to_clean,
            "removed_file_count": len(removed_files),
            "removed_files": removed_files,
        }

    @staticmethod
    def _normalize_file_names(file_names: Sequence[str]) -> List[str]:
        if isinstance(file_names, str):
            raise TypeError("The cleanup file names must be a sequence of names.")

        normalized_file_names: List[str] = []
        for file_name in file_names:
            if not isinstance(file_name, str):
                raise TypeError("Each cleanup file name must be a string.")

            normalized_file_name: str = file_name.strip()
            if (
                not normalized_file_name
                or normalized_file_name in {".", ".."}
                or "/" in normalized_file_name
                or "\\" in normalized_file_name
            ):
                raise ValueError(
                    "Each cleanup entry must be a plain file name."
                )

            if normalized_file_name not in normalized_file_names:
                normalized_file_names.append(normalized_file_name)

        if not normalized_file_names:
            raise ValueError("At least one cleanup file name is required.")

        return normalized_file_names
