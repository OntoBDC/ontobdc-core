import csv
from enum import Enum
import json
from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as synchronize_container_storage_index,
)
from ontobdc.container.plugin.capability.persister.container import (
    StorageContainerMetadataPersisterCapability,
)


class ContainerUpdateSourceKind(str, Enum):
    """
    The kinds of source `--from` accepts.
    """

    CSV_FILE = "csv_file"
    JSON_FILE = "json_file"
    INLINE_ASSIGNMENTS = "inline_assignments"


class ContainerUpdateSource:
    """
    Classifies the value given to `--from` into one of its accepted kinds.
    """

    CSV_SUFFIX: ClassVar[str] = ".csv"
    JSON_SUFFIX: ClassVar[str] = ".json"
    ASSIGNMENT_SEPARATOR: ClassVar[str] = "="

    @classmethod
    def classify(cls, value: str) -> Optional[ContainerUpdateSourceKind]:
        """
        Return the kind of the given source, or None when it is not one.
        """
        source: str = value.strip()
        if not source:
            return None

        suffix: str = Path(source).suffix.lower()
        if suffix == cls.CSV_SUFFIX:
            return ContainerUpdateSourceKind.CSV_FILE

        if suffix == cls.JSON_SUFFIX:
            return ContainerUpdateSourceKind.JSON_FILE

        if cls.ASSIGNMENT_SEPARATOR in source:
            return ContainerUpdateSourceKind.INLINE_ASSIGNMENTS

        return None


class ContainerUpdateSourceParser:
    """
    Convert a declared update source into JSON-compatible key-value data.
    """

    @classmethod
    def parse(
        cls,
        source: str,
        source_kind: ContainerUpdateSourceKind,
    ) -> Dict[str, Any]:
        if source_kind == ContainerUpdateSourceKind.JSON_FILE:
            return cls._parse_json_file(Path(source))

        if source_kind == ContainerUpdateSourceKind.CSV_FILE:
            return cls._parse_csv_file(Path(source))

        if source_kind == ContainerUpdateSourceKind.INLINE_ASSIGNMENTS:
            return cls._parse_inline_assignments(source)

        raise CliCommandArgumentException(
            f"Unsupported container update source: {source}"
        )

    @staticmethod
    def _parse_json_file(source_path: Path) -> Dict[str, Any]:
        if not source_path.is_file():
            raise CliCommandArgumentException(
                f"Container update source file not found: {source_path}"
            )

        parsed_value: Any = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(parsed_value, dict):
            raise CliCommandArgumentException(
                "Container update JSON source must contain an object."
            )

        key: Any
        for key in parsed_value:
            if not isinstance(key, str) or not key.strip():
                raise CliCommandArgumentException(
                    "Container update JSON keys must be non-empty strings."
                )

        return parsed_value

    @staticmethod
    def _parse_csv_file(source_path: Path) -> Dict[str, Any]:
        if not source_path.is_file():
            raise CliCommandArgumentException(
                f"Container update source file not found: {source_path}"
            )

        with source_path.open(encoding="utf-8", newline="") as source_file:
            reader: csv.DictReader = csv.DictReader(source_file)
            rows: List[Dict[Optional[str], Any]] = list(reader)

        if len(rows) != 1:
            raise CliCommandArgumentException(
                "Container update CSV source must contain exactly one data row."
            )

        parsed_value: Dict[str, Any] = {}
        key: Optional[str]
        value: Any
        for key, value in rows[0].items():
            if not isinstance(key, str):
                raise CliCommandArgumentException(
                    "Container update CSV contains values without a header."
                )

            normalized_key: str = key.strip()
            if not normalized_key:
                raise CliCommandArgumentException(
                    "Container update CSV keys must be non-empty strings."
                )
            if not isinstance(value, str):
                raise CliCommandArgumentException(
                    f"Container update CSV value is missing for key: {normalized_key}"
                )

            parsed_value[normalized_key] = value.strip()

        return parsed_value

    @staticmethod
    def _parse_inline_assignments(source: str) -> Dict[str, Any]:
        parsed_value: Dict[str, Any] = {}
        assignment: str
        for assignment in source.split(","):
            key: str
            separator: str
            value: str
            key, separator, value = assignment.partition("=")
            normalized_key: str = key.strip()
            if not separator or not normalized_key:
                raise CliCommandArgumentException(
                    f"Invalid container update assignment: {assignment}"
                )
            if normalized_key in parsed_value:
                raise CliCommandArgumentException(
                    f"Duplicate container update key: {normalized_key}"
                )

            parsed_value[normalized_key] = value.strip()

        return parsed_value


class ContainerUpdateCommand(CliCommandPort):
    """
    Command for updating a registered container from a declared source.
    """

    METADATA = CliCommandMetadata(
        id="ct_update",
        logical_component="container",
        description="Update a registered container from a declared source.",
        arguments=[
            {
                "accepts": [
                    "--from",
                ],
                "valued": True,
                "parameter": "update_source",
                "description": (
                    "Source of values to write into the container's "
                    "metadata and dataset fields. Accepts a path to a "
                    ".csv file, a path to a .json file, or inline "
                    "key=value assignments separated by commas."
                ),
            },
        ],
    )

    UPDATE_FLAG: ClassVar[str] = "--update"
    SOURCE_FLAG: ClassVar[str] = "--from"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container update command at the CLI routing stage.
        """
        if not args or args[0] != "container":
            return False

        return ContainerUpdateCommand._source(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if self._source(self._request.command_args) is None:
            return False

        source_parameter: Any = self._request.context.get_parameter_value(
            "update_source"
        )
        if not isinstance(source_parameter, str):
            return False

        source_value: str = source_parameter.strip()

        return ContainerUpdateSource.classify(source_value) is not None

    @staticmethod
    def _source(scoped_args: List[str]) -> Optional[str]:
        """
        Return the --from value these scoped args name, with --update and
        --from in either order, or None when they do not name one.

        Both flags are required -- there is no bare `container --update`
        with an implicit source -- but which one a user writes first is
        not part of the command's meaning.
        """
        remaining: List[str] = list(scoped_args)
        if ContainerUpdateCommand.UPDATE_FLAG not in remaining:
            return None
        remaining.remove(ContainerUpdateCommand.UPDATE_FLAG)

        if (
            len(remaining) != 2
            or remaining[0] != ContainerUpdateCommand.SOURCE_FLAG
            or not remaining[1].strip()
        ):
            return None

        return remaining[1]

    def run(self) -> CommandResponse:
        """
        Normalize the update source and execute the metadata persister.
        """
        source_parameter: Any = self._request.context.get_parameter_value(
            "update_source"
        )
        if not isinstance(source_parameter, str):
            raise CliCommandArgumentException(
                "Required parameter is missing: update_source"
            )

        source_value: str = source_parameter.strip()
        source_kind: Optional[ContainerUpdateSourceKind] = (
            ContainerUpdateSource.classify(source_value)
        )
        if source_kind is None:
            raise CliCommandArgumentException(
                f"Invalid container update source: {source_value}"
            )

        metadata: Dict[str, Any] = ContainerUpdateSourceParser.parse(
            source_value,
            source_kind,
        )
        self._request.context.set_parameter_value("metadata", metadata)
        capability: StorageContainerMetadataPersisterCapability = (
            StorageContainerMetadataPersisterCapability()
        )
        result: Dict[str, Any] = CapabilityExecutor.execute(
            capability,
            self._request.context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._synchronize_storage_index()

        return CommandResponse(
            title="Container Updated",
            description="Container metadata persisted successfully.",
            content={
                "source": source_value,
                "source_kind": source_kind.value,
                "result": result,
            },
        )

    def _synchronize_storage_index(self) -> None:
        """
        Bring the root storage index back in line with the container metadata.

        The listing reads title and description from the root index, not from
        each container, so persisting metadata without this leaves the listing
        showing what the container said before.
        """
        container_path: Any = self._request.context.get_parameter_value(
            "container_path"
        )
        if not isinstance(container_path, str):
            raise TypeError(
                f"Container path must be a string, got "
                f"{type(container_path).__name__}."
            )

        exit_code: int = synchronize_container_storage_index(
            container_path=container_path,
            root_path=self._request.context.root_path,
        )
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to synchronize the storage index of the container "
                f"at {container_path}."
            )
