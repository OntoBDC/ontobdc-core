"""Container Datasets Healthy Capability.

Runs the dataset-level repair + validation pass for every dataset that is
registered inside the container.  On success it writes the canonical ETL
event file at::

    <container>/.__ontobdc__/etl/container/refresh/container/__container_datasets_healthy__.json

matching the contract expected by the shared
:class:`ontobdc.shared.adapter.worker.StateWorkerAdapter` event lookup and
by the container-refresh state evaluator that derives ``observed_state``
from the persisted event files present on disk.
"""

import os
import json
from typing import Any, Dict, List
from pathlib import Path
import tempfile

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_dataset_healthy.check import (
    evaluate as evaluate_dataset_healthy,
)
from ontobdc.container.plugin.check.is_dataset_healthy.hotfix import (
    main as hotfix_dataset_healthy,
)
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState

class ContainerDatasetsHealthyCapability(TransactionCapability):
    """Repair and validate every dataset registered in the container.

    A hard gate: every dataset is checked, repaired where it fails, and
    checked again. A dataset that is still unhealthy fails the refresh with
    the checks it fails, and the state is not reached.
    """

    ETL_DIRECTORY_NAME: str = "etl"
    ETL_MODULE_NAME: str = "container"
    ETL_PHASE_NAME: str = "refresh"
    ETL_ENTITY_NAME: str = "container"
    ETL_EVENT_FILE_NAME: str = (
        f"{ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY.value}.json"
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_datasets_healthy"
        ),
        version="1.0.0",
        name="Container Datasets Healthy",
        description=(
            "Repair and validate every dataset registered in the "
            "container, failing when one stays unhealthy."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "dataset", "update", "health"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Registered datasets were repaired and validated."
                ),
            },
            "debug_entry": {
                "en": (
                    "Repairing and validating registered datasets and "
                    "producing per-dataset health results."
                ),
            },
        },
    )

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        resolved: Path = Path(container_path).expanduser().resolve()
        return (
            StorageBootstrap.get_ontobdc_directory(resolved)
            / cls.ETL_DIRECTORY_NAME
            / cls.ETL_MODULE_NAME
            / cls.ETL_PHASE_NAME
            / cls.ETL_ENTITY_NAME
            / cls.ETL_EVENT_FILE_NAME
        )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY.description(
            lang
        )

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        return self.event_path(container_path).is_file()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        dataset_paths: List[Path] = RegisteredDatasets.of(container_path)

        previous_dataset_path: Any = context.get_parameter_value("dataset_path")
        results: List[Dict[str, Any]] = []
        try:
            for dataset_path in dataset_paths:
                dataset_path_str: str = str(dataset_path)
                root_path: str = str(context.root_path).strip()
                context.set_parameter_value("dataset_path", dataset_path_str)
                results.append(
                    self._run_dataset_health_pass(
                        dataset_path=dataset_path_str,
                        root_path=root_path,
                    )
                )
        finally:
            if previous_dataset_path is None:
                context.delete_parameter("dataset_path")
            else:
                context.set_parameter_value("dataset_path", previous_dataset_path)

        unhealthy: List[Dict[str, Any]] = [
            result for result in results if not result["healthy"]
        ]
        if unhealthy:
            raise ValueError(
                "Unhealthy datasets after repair: "
                + "; ".join(
                    f"{result['dataset_path']} fails "
                    + ", ".join(
                        sorted(
                            name
                            for name, value in result["evaluation"].items()
                            if value != 0
                        )
                    )
                    for result in unhealthy
                )
            )

        self._write_event(
            container_path,
            payload={
                "dataset_count": len(results),
                "datasets": results,
            },
        )

        return {
            "resulting_state": (
                ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY
            ),
            "container_path": str(container_path),
            "dataset_count": len(results),
            "datasets": results,
        }

    def _write_event(
        self,
        container_path: Path,
        *,
        payload: Dict[str, Any],
    ) -> Path:
        target: Path = self.event_path(container_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        document: Dict[str, Any] = {
            "state": ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY.value,
            "container_path": str(container_path.expanduser().resolve()),
            "phase": self.ETL_PHASE_NAME,
            "entity": self.ETL_ENTITY_NAME,
            "result": payload,
        }
        serialized: str = json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path: Path = Path(handle.name)
            handle.write(serialized + "\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except (OSError, AttributeError):
                pass
        temporary_path.replace(target)
        return target

    @staticmethod
    def _run_dataset_health_pass(
        *,
        dataset_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        """Check a single dataset, repair it when it fails, and evaluate it."""
        healthy: bool = hotfix_dataset_healthy(
            dataset_path=dataset_path,
            root_path=root_path,
        ) == 0
        return {
            "dataset_path": dataset_path,
            "evaluation": evaluate_dataset_healthy(
                dataset_path=dataset_path,
                root_path=root_path,
            ),
            "healthy": healthy,
        }
