from typing import Any, Dict

from rdflib import Graph

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.job.adapter.open_graph import OpenGraph
from ontobdc.job.plugin.machine.job_create.machine import JobCreateRequest
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class GraphOpenedCapability(TransactionCapability):
    """
    Tests that the address is an open graph, and reads it.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.graph_opened",
        version="1.0.0",
        name="Graph Opened",
        description="Test that the address is an open graph, and read it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "graph"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The address is an open graph."},
            "debug_entry": {"en": "Opening the graph of the procedure."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.GRAPH_OPENED.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.GRAPH_OPENED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        url: str = str(JobCreateRequest.required(context, JobCreateRequest.GRAPH_URL_KEY))
        graph: Graph = OpenGraph.load(url)
        context.set_parameter_value(JobCreateRequest.GRAPH_KEY, graph)

        return {"resulting_state": JobCreateProcessState.GRAPH_OPENED, "url": url, "triples": len(graph)}
