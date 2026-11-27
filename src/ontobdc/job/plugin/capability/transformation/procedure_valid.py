from typing import Any, Dict, List, Set

from rdflib import Graph, URIRef

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.job.adapter.procedure_graph import ProcedureGraph
from ontobdc.job.plugin.machine.job_create.machine import JobCreateRequest
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ProcedureValidCapability(TransactionCapability):
    """
    Finds the procedure by the name of its node, and tests it with SHACL.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.procedure_valid",
        version="1.0.0",
        name="Procedure Valid",
        description="Find the procedure by the name of its node and test it against the shape of a procedure.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "procedure", "shacl"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The procedure conforms to the shape of a procedure."},
            "debug_entry": {"en": "Testing the procedure with SHACL."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.PROCEDURE_VALID.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.PROCEDURE_VALID.description(lang)

    @staticmethod
    def _parameters_given(graph: Graph, node: URIRef, name: str, context: CliContextPort) -> None:
        """
        Fails, saying which parameters are missing, when the job is not created with each parameter the procedure
        requires: nothing is created for a job that could not run.
        """
        given: Set[str] = {
            parameter for parameter, _ in JobCreateRequest.required(context, JobCreateRequest.PARAMETERS_KEY)
        }
        missing: List[str] = [
            f"--{required['name'].replace('_', '-')} ({required['label']})"
            + (f": {required['description']}" if required["description"] else "")
            for required in ProcedureGraph.required_parameters(graph, node)
            if required["name"] not in given
        ]
        if missing:
            raise ValueError(
                f"The procedure {name} needs {'the parameter' if len(missing) == 1 else 'the parameters'} "
                f"{'; '.join(missing)}"
            )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph: Graph = JobCreateRequest.required(context, JobCreateRequest.GRAPH_KEY)
        name: str = str(JobCreateRequest.required(context, JobCreateRequest.PROCEDURE_NAME_KEY))
        node: URIRef = ProcedureGraph.node(graph, name)
        ProcedureGraph.validate(graph, node)
        self._parameters_given(graph, node, name, context)
        context.set_parameter_value(JobCreateRequest.PROCEDURE_NODE_KEY, node)

        return {"resulting_state": JobCreateProcessState.PROCEDURE_VALID, "procedure": str(node)}
