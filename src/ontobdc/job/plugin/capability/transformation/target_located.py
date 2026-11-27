from typing import Any, Dict

from rdflib import Graph, URIRef

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.job.adapter.job_target import JobTarget
from ontobdc.job.adapter.procedure_graph import ProcedureGraph
from ontobdc.job.plugin.machine.job_create.machine import JobCreateRequest
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class TargetLocatedCapability(TransactionCapability):
    """
    Finds, by its id, what the procedure executes, among the machines and the capabilities of every module.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.target_located",
        version="1.0.0",
        name="Target Located",
        description="Find the machine or the capability the procedure targets, by its id.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "procedure", "target"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The target of the procedure was found."},
            "debug_entry": {"en": "Looking for the target of the procedure."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.TARGET_LOCATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.TARGET_LOCATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph: Graph = JobCreateRequest.required(context, JobCreateRequest.GRAPH_KEY)
        node: URIRef = JobCreateRequest.required(context, JobCreateRequest.PROCEDURE_NODE_KEY)
        target: JobTarget = JobTarget.locate(ProcedureGraph.target(graph, node))
        context.set_parameter_value(JobCreateRequest.TARGET_KEY, target.id)

        return {"resulting_state": JobCreateProcessState.TARGET_LOCATED, "target": target.id, "kind": target.kind}
