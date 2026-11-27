from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.plugin.capability.transformation.dataset_found import DatasetFoundCapability
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.job.adapter.job_store import JobStore
from ontobdc.job.plugin.machine.job_create.machine import JobCreateRequest
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class JobDatasetReadyCapability(TransactionCapability):
    """
    Makes sure the container has a dataset for jobs, and creates it when it has none.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.job_dataset_ready",
        version="1.0.0",
        name="Job Dataset Ready",
        description="Make sure the container has a dataset for jobs, and create it when it has none.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "dataset", "container"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The container has a dataset for jobs."},
            "debug_entry": {"en": "Looking for the dataset of jobs of the container."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.JOB_DATASET_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.JOB_DATASET_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            str(JobCreateRequest.required(context, JobCreateRequest.CONTAINER_PATH_KEY))
        ).expanduser().resolve()
        existing: Optional[Path] = EntityDatasets.first(container_path, JobStore.ENTITY_IRI)
        dataset_path: Path
        if existing is not None:
            dataset_path = existing
        else:
            # The path of the container is the one the context already has, and stays: the states after this one read it.
            keys: List[str] = [
                EntityWriteRequest.ENTITY_IRI_KEY,
                EntityWriteRequest.DATASET_PATH_KEY,
                "dataset_title",
            ]
            context.set_parameter_value(EntityWriteRequest.ENTITY_IRI_KEY, JobStore.ENTITY_IRI)
            try:
                dataset_path = Path(DatasetFoundCapability().execute(context)["dataset_path"])
            finally:
                key: str
                for key in keys:
                    context.delete_parameter(key)

        context.set_parameter_value(JobCreateRequest.DATASET_PATH_KEY, str(dataset_path))

        return {
            "resulting_state": JobCreateProcessState.JOB_DATASET_READY,
            "dataset_path": str(dataset_path),
            "created": existing is None,
        }
