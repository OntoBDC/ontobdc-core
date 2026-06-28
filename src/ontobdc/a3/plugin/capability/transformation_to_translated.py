
import json
import requests
from pathlib import Path
from rdflib.namespace import RDF
from typing import Any, Dict, Optional
from rdflib import Graph, Literal, URIRef
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a32.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.a32.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata

SH = get_ontology_by_prefix("sh")


class TransformationToTranslatedCapability(TransformationCapability):
    """
    Transformation capability to translate the input data to a translated format.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.translated",
        version="0.1.0",
        name="Data package transformation to Translated",
        description="Transform a data package to a translated version.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "translated", "transformation"],
            "pt": ["dados", "traduzido", "transformação"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to transform.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The parsed data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.TRANSLATED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Translated",
            "pt": "Transformação de pacote de dados para Traduzido",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Transform a data package to a translated version.",
            "pt": "Transforma um pacote de dados para uma versão traduzida.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Execute the transformation capability.
        """
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")

        raw_path: Path = etl_package_path.path / "parsed.json"

        guardrail_schema_uri = "http://ontobdc.org/ontology/social/shp.ttl#JobOfferShape"

        parsed_data: Dict[str, Any] = json.loads(raw_path.read_text(encoding="utf-8"))
        graph: Graph = self._translate_to_graph(parsed_data, guardrail_schema_uri)

        graph_path: Path = etl_package_path.path / "graph.ttl"
        graph.serialize(destination=str(graph_path), format="turtle")

        return TransformationResponse(resultingState=A3EtlProcessState.TRANSLATED)

    def _translate_to_graph(self, data: Dict[str, Any], schema_uri: str) -> Graph:
        ontology_uri = schema_uri.split("#")[0]

        response = requests.get(ontology_uri, timeout=10)
        response.raise_for_status()

        shape_graph = Graph()
        shape_graph.parse(data=response.text, format="turtle", publicID=ontology_uri)

        shape_node = URIRef(schema_uri)
        target_class = shape_graph.value(shape_node, SH.targetClass)
        if target_class is None:
            raise ValueError(f"No sh:targetClass found for shape '{schema_uri}'.")

        subject_name = data.get("name")
        if not isinstance(subject_name, str) or not subject_name.strip():
            raise ValueError("Parsed data must contain a non-empty 'name' to build the subject URI.")

        subject = URIRef(f"{ontology_uri}#{subject_name.strip()}")
        graph = Graph()

        for prefix, namespace in shape_graph.namespaces():
            graph.bind(prefix, namespace)

        graph.add((subject, RDF.type, target_class))

        lang = data.get("inLanguage")
        if not isinstance(lang, str) or not lang.strip():
            lang = None

        for prop_blank in shape_graph.objects(shape_node, SH.property):
            path_uri = shape_graph.value(prop_blank, SH.path)
            if not isinstance(path_uri, URIRef):
                continue

            prop_name = self._local_name(path_uri)
            if prop_name not in data:
                continue

            value = data[prop_name]
            if value in (None, ""):
                continue

            if isinstance(value, list):
                if not value:
                    continue
                for item in value:
                    literal = self._to_literal(item, prop_blank, shape_graph, lang)
                    graph.add((subject, path_uri, literal))
            else:
                literal = self._to_literal(value, prop_blank, shape_graph, lang)
                graph.add((subject, path_uri, literal))

        return graph

    def _to_literal(
        self,
        value: Any,
        prop_blank: URIRef,
        shape_graph: Graph,
        lang: Optional[str],
    ) -> Literal:
        if not isinstance(value, str):
            value = str(value)

        value = self._normalize_enum_value(value, prop_blank, shape_graph)

        if self._is_multilang_property(prop_blank, shape_graph) and lang:
            return Literal(value, lang=lang)

        datatype = shape_graph.value(prop_blank, SH.datatype)
        if datatype is not None:
            if str(datatype) == "http://www.w3.org/2001/XMLSchema#string":
                return Literal(value)
            return Literal(value, datatype=datatype)

        return Literal(value)

    def _is_multilang_property(self, prop_blank: URIRef, shape_graph: Graph) -> bool:
        or_node = shape_graph.value(prop_blank, URIRef("http://www.w3.org/ns/shacl#or"))
        if or_node is None:
            return False

        for member in shape_graph.items(or_node):
            datatype = shape_graph.value(member, SH.datatype)
            if datatype == RDF.langString:
                return True

        return False

    def _normalize_enum_value(self, value: str, prop_blank: URIRef, shape_graph: Graph) -> str:
        enum_list = shape_graph.value(prop_blank, SH["in"])
        if enum_list is None:
            return value

        normalized_value = self._canonicalize_token(value)
        for member in shape_graph.items(enum_list):
            candidate = str(member)
            if self._canonicalize_token(candidate) == normalized_value:
                return candidate

        return value

    def _canonicalize_token(self, value: str) -> str:
        return "".join(ch for ch in value.lower().strip() if ch.isalnum())

    def _local_name(self, uri: URIRef) -> str:
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        if "/" in uri_str:
            return uri_str.rsplit("/", 1)[-1]
        return uri_str
