from typing import Callable, ClassVar, List, Tuple
from pathlib import Path
from functools import partial

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.shared.adapter.capability import HealthCheckCapability
from ontobdc.shared.domain.model.health import HealthCheck
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_dataset_healthy.check import (
    main as check_dataset_healthy,
)
from ontobdc.container.plugin.check.is_container_cleaned.check import (
    main as check_container_cleaned,
)
from ontobdc.container.plugin.check.is_dataset_facade_valid.check import (
    main as check_dataset_facade_valid,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_structure_valid.check import (
    main as check_dataset_structure_valid,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.check import (
    main as check_container_datapackage_updated,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)
from ontobdc.container.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    main as check_container_datapackage_ro_crate_synced,
)
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_container_datapackage_frictionless_valid,
)

# Every check script answers the same way — zero when what it looked at is
# in order — and differs only in what it is pointed at: a container check
# takes the container, a dataset check takes the dataset. Both also take
# the storage root the subject lives under.
ContainerCheck = Callable[..., int]
DatasetCheck = Callable[..., int]


class ContainerHealthCheckCapability(HealthCheckCapability):
    """
    Reports the verifications that say whether a container is in order.

    The container is checked with the six verifications
    ``ContainerHealthyCapability`` repairs, plus the cleaning check
    ``ContainerCleanedCapability`` repairs, and each dataset the container
    registers is checked with five of its own. What separates this
    capability from those is that this one only looks.

    ``dataset_healthy`` is a roll-up: it already contains the four
    dataset checks listed beside it, plus the dataset's own Data Package
    and surfaceable-marker checks. It is reported alongside them on
    purpose — the roll-up says whether a dataset is in order, the parts
    say where it is not.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    # The stray files a container is expected to be free of. The cleaning
    # check carries no list of its own — it answers about the names it is
    # given — so the capability that reports it names them, the same two
    # ContainerCleanedCapability removes.
    CLEANABLE_FILE_NAMES: ClassVar[Tuple[str, ...]] = (".DS_Store", "__pycache__")

    # The reported verifications, in reading order: the check script that
    # answers each one, and the label a reader sees beside its outcome.
    REPORTED_CONTAINER_CHECKS: ClassVar[
        Tuple[Tuple[str, ContainerCheck, str], ...]
    ] = (
        (
            "container_metadata_ready",
            check_container_metadata_ready,
            "Container metadata",
        ),
        (
            "container_storage_index_ready",
            check_container_storage_index_ready,
            "Storage index entry",
        ),
        (
            "container_cleaned",
            partial(check_container_cleaned, file_names=CLEANABLE_FILE_NAMES),
            "Free of stray files",
        ),
        (
            "container_datapackage_updated",
            check_container_datapackage_updated,
            "Data Package against the files",
        ),
        (
            "container_manifest_synced",
            check_container_manifest_synced,
            "RO-Crate manifest",
        ),
        (
            "container_datapackage_frictionless_valid",
            check_container_datapackage_frictionless_valid,
            "Data Package validity",
        ),
        (
            "container_datapackage_ro_crate_synced",
            check_container_datapackage_ro_crate_synced,
            "Data Package against RO-Crate",
        ),
    )

    REPORTED_DATASET_CHECKS: ClassVar[
        Tuple[Tuple[str, DatasetCheck, str], ...]
    ] = (
        (
            "dataset_healthy",
            check_dataset_healthy,
            "Dataset health",
        ),
        (
            "dataset_structure_valid",
            check_dataset_structure_valid,
            "Dataset structure",
        ),
        (
            "dataset_metadata_ready",
            check_dataset_metadata_ready,
            "Dataset metadata",
        ),
        (
            "dataset_container_index_ready",
            check_dataset_container_index_ready,
            "Container index entry",
        ),
        (
            "dataset_facade_valid",
            check_dataset_facade_valid,
            "Facade",
        ),
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.health.container_health",
        version="1.0.0",
        name="Container Health Check",
        description=(
            "Report whether a container carries valid metadata, a "
            "synchronized storage index entry, an RO-Crate manifest and a "
            "Data Package in step with its files, and whether every "
            "dataset it registers is itself in order."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "dataset", "health", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Container Health Check"

    def description(self, lang: str = "en") -> str:
        return "Reports the verifications that say whether a container is in order."

    def checks(self, context: CliContextPort) -> List[HealthCheck]:
        """
        Run every verification, on the container and on each dataset.
        """
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        if not container_path.is_dir():
            raise ValueError(
                f"Container path is not an accessible directory: {container_path}"
            )

        root_path: Path = Path(context.root_path).expanduser().resolve()

        checks: List[HealthCheck] = self._container_checks(container_path, root_path)
        dataset_path: Path
        for dataset_path in RegisteredDatasets.of(container_path):
            checks.extend(self._dataset_checks(dataset_path, root_path))

        return checks

    def _container_checks(
        self,
        container_path: Path,
        root_path: Path,
    ) -> List[HealthCheck]:
        """
        Run the verifications that are about the container itself.
        """
        checks: List[HealthCheck] = []
        identifier: str
        check: ContainerCheck
        label: str
        for identifier, check, label in self.REPORTED_CONTAINER_CHECKS:
            checks.append(
                HealthCheck(
                    identifier=identifier,
                    label=label,
                    passed=check(
                        container_path=str(container_path),
                        root_path=str(root_path),
                    ) == 0,
                )
            )

        return checks

    def _dataset_checks(
        self,
        dataset_path: Path,
        root_path: Path,
    ) -> List[HealthCheck]:
        """
        Run the verifications that are about one registered dataset.
        """
        checks: List[HealthCheck] = []
        identifier: str
        check: DatasetCheck
        label: str
        for identifier, check, label in self.REPORTED_DATASET_CHECKS:
            checks.append(
                HealthCheck(
                    identifier=identifier,
                    label=label,
                    passed=check(
                        dataset_path=str(dataset_path),
                        root_path=str(root_path),
                    ) == 0,
                    scope=dataset_path.name,
                )
            )

        return checks
