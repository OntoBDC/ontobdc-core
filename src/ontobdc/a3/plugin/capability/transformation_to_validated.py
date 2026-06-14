
import json
import requests
from pathlib import Path
from rdflib import Graph
from typing import Any, Dict
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a3.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class TransformationToValidatedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.validated",
        version="0.1.0",
        name="Data package transformation to Validated",
        description="Validate a translated RDF graph against the target SHACL shape.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "validated", "transformation", "shacl"],
            "pt": ["dados", "validado", "transformação", "shacl"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to validate.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The validated data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.VALIDATED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Validated",
            "pt": "Transformação de pacote de dados para Validado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Validate a translated RDF graph against the target SHACL shape.",
            "pt": "Valida um grafo RDF traduzido contra a forma SHACL alvo.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")

        graph_path = etl_package_path.path / "graph.ttl"
        validated_path = etl_package_path.path / "validated.txt"
        error_path = etl_package_path.path / "err.json"
        guardrail_schema_uri = "http://ontobdc.org/ontology/social/shp.ttl#JobOfferShape"

        try:
            report_text = self._validate_graph(graph_path, guardrail_schema_uri)
            validated_path.write_text(report_text, encoding="utf-8")

            if error_path.exists():
                error_path.unlink()
        except Exception as exc:
            error_payload = {
                "state": A3EtlProcessState.TRANSLATED.value,
                "error": str(exc),
            }
            error_path.write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            raise

        return TransformationResponse(resultingState=A3EtlProcessState.VALIDATED)

    def _validate_graph(self, graph_path: Path, guardrail_schema_uri: str) -> str:
        try:
            from pyshacl import validate as shacl_validate
        except ImportError as exc:
            raise RuntimeError("pyshacl is required to validate graph.ttl against SHACL.") from exc

        ontology_uri = guardrail_schema_uri.split("#")[0]
        response = requests.get(ontology_uri, timeout=10)
        response.raise_for_status()

        data_graph = Graph()
        data_graph.parse(graph_path, format="turtle")

        shacl_graph = Graph()
        shacl_graph.parse(data=response.text, format="turtle", publicID=ontology_uri)

        conforms, report_graph, report_text = shacl_validate(
            data_graph=data_graph,
            shacl_graph=shacl_graph,
        )

        if not conforms:
            message = report_text.strip() if isinstance(report_text, str) and report_text.strip() else "SHACL validation failed."
            raise ValueError(message)

        if isinstance(report_text, str) and report_text.strip():
            return report_text

        return report_graph.serialize(format="turtle")
