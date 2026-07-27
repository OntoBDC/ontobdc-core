
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.plugin.check.has_valid_context.check import main as check_has_valid_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_has_valid_context
from ontobdc.shared.adapter.util import to_snake_case
from ontobdc.storage.adapter.bootstrap import get_context_file_path


class ContextEntityCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="entity",
        logical_component="context",
        description="Display the persisted information for a context entity.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Display the persisted information for a context entity.",
                "usage": "ontobdc context --entity <entity_uri>",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._entity_payload: Optional[Dict[str, Any]] = None

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 3 and args[0] == "context" and args[1] == "--entity"

    def check(self) -> bool:
        # command_args: List[str] = list(self._request.command_args)
        # if len(command_args) != 2 or command_args[0] != "--entity":
        #     raise CliCommandArgumentException("Usage: ontobdc context --entity <entity_uri>")

        # entity_uri: str = str(self._request.context.get_parameter_value("entity_uri") or "").strip()
        # if not entity_uri:
        #     raise CliCommandArgumentException("Usage: ontobdc context --entity <entity_uri>")

        # root_path: str = str(self._request.context.root_path)
        # if check_has_valid_context(root_path=root_path) != 0:
        #     hotfix_has_valid_context(root_path=root_path)
        #     self._request.context.reload()

        # if check_has_valid_context(root_path=root_path) != 0:
        #     raise CliCommandArgumentException("Invalid context data.")

        # entity_payload: Optional[Dict[str, Any]] = self._load_entity_payload(entity_uri)
        # if entity_payload is None:
        #     raise CliCommandArgumentException(f"Entity not found in context: {entity_uri}")

        # self._entity_payload = entity_payload
        return True

    def run(self) -> CommandResponse:
        entity_uri: str = str(self._request.context.get_parameter_value("entity_uri") or "").strip()

        entity_payload = {
            "entity_uri": entity_uri,
        }

        return CommandResponse(
            title="OntoBDC Context Entity",
            description=f"Display the persisted information for entity '{entity_uri}'.",
            content=entity_payload,
        )
        # try:
        #     entity_payload: Optional[Dict[str, Any]] = self._entity_payload or self._load_entity_payload(entity_uri)
        #     if entity_payload is None:
        #         raise ValueError(f"Entity not found in context: {entity_uri}")

        #     return CommandResponse(
        #         title="OntoBDC Context Entity",
        #         description=f"Display the persisted information for entity '{entity_uri}'.",
        #         content=entity_payload,
        #     )
        # except Exception as exc:
        #     return ExceptionCommandResponse(
        #         title="OntoBDC Context Entity Failed",
        #         description=f"Could not display the persisted information for entity '{entity_uri}'.",
        #         content={
        #             "entity_uri": entity_uri,
        #             "error": str(exc),
        #         },
        #     )

    # def _load_entity_payload(self, entity_uri: str) -> Optional[Dict[str, Any]]:
    #     root_path: Path = Path(str(self._request.context.root_path)).expanduser().resolve()
    #     context_file_path: Path = Path(str(get_context_file_path(root_path=root_path))).expanduser().resolve()

    #     context_graph: Graph = Graph()
    #     context_graph.parse(str(context_file_path), format="turtle")

    #     entity_ref: URIRef = URIRef(entity_uri)
    #     entity_data: Dict[str, Any] = self._collect_subject_data(context_graph, entity_ref)
    #     learning_records: List[Dict[str, Any]] = self._collect_learning_records(context_graph, entity_ref)

    #     if not entity_data and not learning_records:
    #         return None

    #     return {
    #         "entity_uri": entity_uri,
    #         "entity": entity_data,
    #         "learning_record_count": len(learning_records),
    #         "learning_records": learning_records,
    #         "context_file": str(context_file_path),
    #     }

    # def _collect_learning_records(self, context_graph: Graph, entity_ref: URIRef) -> List[Dict[str, Any]]:
    #     learning_records: List[Dict[str, Any]] = []
    #     record_ref: URIRef
    #     for record_ref in sorted(set(context_graph.subjects()), key=str):
    #         if not self._subject_matches_entity(context_graph, record_ref, entity_ref):
    #             continue

    #         learning_record: Dict[str, Any] = self._collect_subject_data(context_graph, record_ref)
    #         learning_record["record_uri"] = str(record_ref)
    #         learning_records.append(learning_record)

    #     learning_records.sort(
    #         key=lambda record: str(record.get("learned_at") or ""),
    #         reverse=True,
    #     )
    #     return learning_records

    # def _subject_matches_entity(self, context_graph: Graph, subject: URIRef, entity_ref: URIRef) -> bool:
    #     predicate: URIRef
    #     obj: Any
    #     for predicate, obj in context_graph.predicate_objects(subject):
    #         if self._predicate_name(predicate) != "entity_uri":
    #             continue
    #         if str(obj) == str(entity_ref):
    #             return True

    #     return False

    # def _collect_subject_data(self, context_graph: Graph, subject: URIRef) -> Dict[str, Any]:
    #     subject_data: Dict[str, Any] = {}
    #     predicate: URIRef
    #     obj: Any
    #     for predicate, obj in context_graph.predicate_objects(subject):
    #         if predicate == RDF.type and obj == OWL.NamedIndividual:
    #             continue

    #         predicate_name: str = self._predicate_name(predicate)
    #         predicate_value: Any = self._object_value(obj)
    #         existing_value: Optional[Any] = subject_data.get(predicate_name)

    #         if existing_value is None:
    #             subject_data[predicate_name] = predicate_value
    #             continue

    #         if isinstance(existing_value, list):
    #             existing_value.append(predicate_value)
    #             continue

    #         subject_data[predicate_name] = [existing_value, predicate_value]

    #     return subject_data

    # def _predicate_name(self, predicate: URIRef) -> str:
    #     predicate_value: str = str(predicate)
    #     if "#" in predicate_value:
    #         return to_snake_case(predicate_value.split("#")[-1].strip())

    #     return to_snake_case(predicate_value.rstrip("/").split("/")[-1].strip())

    # def _object_value(self, obj: Any) -> Any:
    #     if isinstance(obj, Literal):
    #         literal_value: Any = obj.toPython()
    #         if isinstance(literal_value, str):
    #             stripped_literal_value: str = literal_value.strip()
    #             if stripped_literal_value.startswith("[") or stripped_literal_value.startswith("{"):
    #                 try:
    #                     return json.loads(stripped_literal_value)
    #                 except ValueError:
    #                     return literal_value
    #         return literal_value

    #     if isinstance(obj, URIRef):
    #         return str(obj)

    #     return str(obj)
