
import shutil
from pathlib import Path
from typing import Any, Dict
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a3.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class TransformationToReasonedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.reasoned",
        version="0.1.0",
        name="Data package transformation to Reasoned",
        description="Create a reasoned.ttl artifact as a copy of graph.ttl.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "reasoned", "transformation"],
            "pt": ["dados", "inferido", "transformação"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to reason over.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The reasoned data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.REASONED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Reasoned",
            "pt": "Transformação de pacote de dados para Inferido",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Create a reasoned.ttl artifact as a copy of graph.ttl.",
            "pt": "Cria um artefato reasoned.ttl como cópia de graph.ttl.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")

        graph_path = etl_package_path.path / "graph.ttl"
        reasoned_path = etl_package_path.path / "reasoned.ttl"

        shutil.copyfile(graph_path, reasoned_path)

        return TransformationResponse(resultingState=A3EtlProcessState.REASONED)
