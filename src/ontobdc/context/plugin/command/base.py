
import json
import os
from typing import Any, Dict, Optional
from ontobdc.cli import get_config_dir
from rdflib import Graph, Literal, URIRef, RDF
from rdflib.namespace import OWL

from ontobdc.context import get_context_file
from ontobdc.shared.adapter.util import to_snake_case
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.cli.domain.resource.command import ExceptionCommandResponse, ReportCommandResponse

OBDC = get_ontology_by_prefix("obdc")


class ContextBaseCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="context",
        description="Display the persisted execution context.",
        arguments=[
            {
                "accepts": [],
                "description": "Display the persisted execution context.",
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        if not len(self._request.command_args) == 0:
            return False

        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            context_file_path: str = get_context_file()
            context_data: Dict[str, Any] = self._load_context_data(context_file_path)

            return ReportCommandResponse(
                title="OntoBDC Context",
                description="Display the persisted execution context.",
                content={
                    "context": context_data,
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="OntoBDC Context",
                description="Failed to display the persisted execution context.",
                content={
                    "execution_response": str(error),
                },
            )

    def _load_context_data(self, context_file_path: str) -> Dict[str, Any]:
        context_graph: Graph = Graph()
        context_graph.parse(context_file_path, format="turtle")

        context_individual: Optional[URIRef] = None
        for subject in context_graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            context_individual = subject
            break

        if not isinstance(context_individual, URIRef):
            return {}

        context_data: Dict[str, Any] = {}
        for predicate, obj in context_graph.predicate_objects(context_individual):
            if predicate == RDF.type:
                continue
            if predicate == OWL.NamedIndividual:
                continue

            predicate_name: str = self._predicate_name(predicate)
            context_data[predicate_name] = self._object_value(obj)

        context_dir_path: str = os.path.dirname(context_file_path)
        context_data["parsed_intent"] = self._load_intent_metadata(
            os.path.join(context_dir_path, IntentScoreResponse.PARSED_INTENT_FILE_NAME)
        )

        context_data["canonicalized_intent"] = self._load_canonicalized_intent_metadata(
            os.path.join(context_dir_path, IntentScoreResponse.CANONICALIZED_INTENT_FILE_NAME)
        )

        return context_data

    def _predicate_name(self, predicate: URIRef) -> str:
        predicate_value: str = str(predicate)
        if "#" in predicate_value:
            return to_snake_case(predicate_value.split("#")[-1].strip())

        return to_snake_case(predicate_value.rstrip("/").split("/")[-1].strip())

    def _object_value(self, obj: Any) -> Any:
        if isinstance(obj, Literal):
            return obj.toPython()

        if isinstance(obj, URIRef):
            return str(obj)

        return str(obj)

    def _load_intent_metadata(self, file_path: str) -> Dict[str, Any]:
        intent_root: Optional[Dict[str, Any]] = None

        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as intent_file:
                intent_data: Dict[str, Any] = json.load(intent_file)
            has_root: Any = intent_data.get("hasRoot", [])
            if isinstance(has_root, list) and len(has_root) > 0 and isinstance(has_root[0], dict):
                intent_root = has_root[0]

        return {
            "file_path": f"./{file_path.split(get_config_dir())[-1].strip('/')}",
            "root": intent_root,
        }

    def _load_canonicalized_intent_metadata(self, file_path: str) -> Dict[str, Any]:
        canonicalized_intent_data: Dict[str, Any] = self._load_intent_metadata(file_path)

        if not os.path.isfile(file_path):
            canonicalized_intent_data["matching_capabilities"] = []
            canonicalized_intent_data["supporting_capabilities"] = []
            return canonicalized_intent_data

        with open(file_path, "r", encoding="utf-8") as intent_file:
            intent_data: Dict[str, Any] = json.load(intent_file)

        has_matching_capability: Any = intent_data.get("hasMatchingCapability", [])
        if isinstance(has_matching_capability, list):
            canonicalized_intent_data["matching_capabilities"] = has_matching_capability
        else:
            canonicalized_intent_data["matching_capabilities"] = []

        has_supporting_capability: Any = intent_data.get("hasSupportingCapability", [])
        if isinstance(has_supporting_capability, list):
            canonicalized_intent_data["supporting_capabilities"] = has_supporting_capability
        else:
            canonicalized_intent_data["supporting_capabilities"] = []

        return canonicalized_intent_data
