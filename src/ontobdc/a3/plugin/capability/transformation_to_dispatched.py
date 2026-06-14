
import re
import time
from pathlib import Path
from typing import Any, Dict
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a3.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class TransformationToDispatchedCapability(TransformationCapability):
    SHAPE_URI = "http://ontobdc.org/ontology/social/shp.ttl#JobOfferShape"

    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.dispatched",
        version="0.1.0",
        name="Data package transformation to Dispatched",
        description="Dump graph.ttl as dispatched.jsonld.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "dispatched", "transformation", "jsonld"],
            "pt": ["dados", "despachado", "transformação", "jsonld"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to dispatch.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The dispatched data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.DISPATCHED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Dispatched",
            "pt": "Transformação de pacote de dados para Despachado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Dump graph.ttl as dispatched.jsonld.",
            "pt": "Exporta graph.ttl como dispatched.jsonld.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")

        graph_path = etl_package_path.path / "graph.ttl"
        event_path = etl_package_path.path / "dispatched.jsonld"

        graph = Graph()
        graph.parse(graph_path, format="turtle")
        event_graph = self._build_event_graph(graph, etl_package_path.path.name)
        event_graph.serialize(destination=str(event_path), format="json-ld", indent=2)

        return TransformationResponse(resultingState=A3EtlProcessState.DISPATCHED)

    def _build_event_graph(self, graph: Graph, package_id: str) -> Graph:
        source_subject = self._get_primary_subject(graph)
        event_uri = URIRef(self._build_event_uri(source_subject, package_id))

        event_graph = Graph()
        for prefix, namespace in graph.namespaces():
            event_graph.bind(prefix, namespace)

        for subj, pred, obj in graph:
            new_subj = event_uri if subj == source_subject else subj
            new_obj = event_uri if obj == source_subject else obj
            event_graph.add((new_subj, pred, new_obj))

        return event_graph

    def _get_primary_subject(self, graph: Graph) -> URIRef:
        for subject in graph.subjects(RDF.type, None):
            if isinstance(subject, URIRef):
                return subject

        for subject in graph.subjects():
            if isinstance(subject, URIRef):
                return subject

        raise ValueError("graph.ttl does not contain a URI subject to dispatch.")

    def _build_event_uri(self, _subject: URIRef, package_id: str) -> str:
        entity_name = self._shape_entity_name(self.SHAPE_URI)
        timestamp = int(time.time())
        return f"urn:{entity_name}:event/{package_id}/{timestamp}"

    def _shape_entity_name(self, subject_uri: str) -> str:
        local_name = subject_uri.split("#")[-1] if "#" in subject_uri else subject_uri.rsplit("/", 1)[-1]
        sanitized_name = re.sub(r"^[^A-Za-z]*", "", local_name)
        if not sanitized_name:
            sanitized_name = "resource"

        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[0-9]+", sanitized_name)
        if not parts:
            parts = [sanitized_name]

        normalized = "_".join(part.lower() for part in parts)
        normalized = re.sub(r"_?shape$", "", normalized)
        return normalized or "resource"
