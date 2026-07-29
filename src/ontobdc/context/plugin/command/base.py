import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.plugin.check.has_valid_context.check import main as check_has_valid_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_has_valid_context
from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.adapter.util import to_snake_case
from ontobdc.storage.adapter.bootstrap import get_context_file_path

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


class ContextBaseCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="context",
        description="Display the persisted execution context.",
        depends_on=None,
        arguments=[
            {
                "accepts": [],
                "description": "Display the persisted execution context.",
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return not args or (args[0] == "context" and len(args) == 1)

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        if not self.accepts(self._request.command_args):
            return False

        root_path: str = str(self._request.context.root_path)
        if check_has_valid_context(root_path=root_path) != 0:
            hotfix_has_valid_context(root_path=root_path)
            self._request.context.reload()

        return check_has_valid_context(root_path=root_path) == 0

    def run(self) -> CommandResponse:
        try:
            root_path: str = str(self._request.context.root_path)
            context_file_path: str = str(get_context_file_path(root_path=Path(root_path).expanduser().resolve()))
            context_data: Dict[str, Any] = self._load_context_data(context_file_path)

            return CommandResponse(
                title="OntoBDC Context",
                description="Display the persisted execution context.",
                content={"context": context_data},
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="OntoBDC Context",
                description="Failed to display the persisted execution context.",
                content={"error": str(error)},
            )

    def _load_context_data(self, context_file_path: str) -> Dict[str, Any]:
        context_graph: Graph = Graph()
        context_graph.parse(context_file_path, format="turtle")

        context_individual: Optional[URIRef] = None
        subject: URIRef
        for subject in context_graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            context_individual = subject
            break

        if not isinstance(context_individual, URIRef):
            return {}

        context_data: Dict[str, Any] = {}
        predicate: URIRef
        obj: Any
        for predicate, obj in context_graph.predicate_objects(context_individual):
            if predicate == RDF.type:
                continue
            if predicate == OWL.NamedIndividual:
                continue

            predicate_name: str = self._predicate_name(predicate)
            context_data[predicate_name] = self._object_value(obj)

        context_dir_path: str = os.path.dirname(context_file_path)
        parsed_intent_path: str = os.path.join(context_dir_path, "parsed_intent.json")
        parsed_intent: Optional[Dict[str, Any]] = self._load_intent_metadata(parsed_intent_path)
        if parsed_intent is not None:
            context_data["parsed_intent"] = parsed_intent

        canonicalized_intent_path: str = os.path.join(context_dir_path, "canonicalized_intent.json")
        canonicalized_intent: Optional[Dict[str, Any]] = self._load_canonicalized_intent_metadata(
            canonicalized_intent_path
        )
        if canonicalized_intent is not None:
            context_data["canonicalized_intent"] = canonicalized_intent

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

    def _load_intent_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        intent_root: Optional[Dict[str, Any]] = None
        if not os.path.isfile(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as intent_file:
            intent_data: Dict[str, Any] = json.load(intent_file)

        has_root: Any = intent_data.get("hasRoot", [])
        if isinstance(has_root, list) and len(has_root) > 0 and isinstance(has_root[0], dict):
            intent_root = has_root[0]

        if intent_root is None:
            return None

        config_dir: str = str(ConfigDataAdapter().config_dir)
        relative_path: str = file_path.split(config_dir)[-1].strip("/")
        return {
            "file_path": f"./{relative_path}",
            "root": intent_root,
        }

    def _load_canonicalized_intent_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isfile(file_path):
            return None

        canonicalized_intent_data: Optional[Dict[str, Any]] = self._load_intent_metadata(file_path)
        if canonicalized_intent_data is None:
            return None

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
