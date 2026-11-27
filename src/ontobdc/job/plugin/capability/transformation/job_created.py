from pathlib import Path
from typing import Any, Dict, List, Tuple

from rdflib import Graph, URIRef

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.job.adapter.job_store import JobStore
from ontobdc.job.plugin.machine.job_create.machine import JobCreateRequest
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class JobCreatedCapability(TransactionCapability):
    """
    Creates the job in the dataset of jobs, with its run waiting to start. Nothing is run here.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.job_created",
        version="1.0.0",
        name="Job Created",
        description="Create the job in the dataset of jobs, with its run waiting to start.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "entity", "write"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The job was created and is pending."},
            "debug_entry": {"en": "Creating the job."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.JOB_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.JOB_CREATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph: Graph = JobCreateRequest.required(context, JobCreateRequest.GRAPH_KEY)
        procedure: URIRef = JobCreateRequest.required(context, JobCreateRequest.PROCEDURE_NODE_KEY)
        dataset_path: Path = Path(str(JobCreateRequest.required(context, JobCreateRequest.DATASET_PATH_KEY)))
        parameters: List[Tuple[str, str]] = JobCreateRequest.required(context, JobCreateRequest.PARAMETERS_KEY)
        job_id: str = JobStore.create(
            dataset_path,
            str(JobCreateRequest.required(context, JobCreateRequest.GRAPH_URL_KEY)),
            graph,
            procedure,
            parameters,
        )
        context.set_parameter_value(JobCreateRequest.JOB_ID_KEY, job_id)

        return {"resulting_state": JobCreateProcessState.JOB_CREATED, "job_id": job_id}
