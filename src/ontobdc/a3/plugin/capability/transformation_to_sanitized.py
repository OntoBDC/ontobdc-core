
import re
from pathlib import Path
from typing import Any, Dict
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a3.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class TransformationToSanitizedCapability(TransformationCapability):
    """
    Capability for transforming a package to a sanitized version.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.sanitized",
        version="0.1.0",
        name="Data package transformation to Sanitized",
        description="Transform a data package to a sanitized version.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "sanitized", "transformation"],
            "pt": ["dados", "sanitizado", "transformação"],
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
                    "description": "The sanitized data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.SANITIZED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Sanitized",
            "pt": "Transformação de pacote de dados para Sanitizado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Transform a data package to a sanitized version.",
            "pt": "Transforma um pacote de dados para uma versão sanitizada.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")

        raw_path = etl_package_path.path / "raw.txt"
        sanitized_path = etl_package_path.path / "sanitized.txt"

        with open(raw_path, "r", encoding="utf-8") as f:
            content = f.read()

        clean_content = re.sub(r"<[^>]+>", "", content)

        with open(sanitized_path, "w", encoding="utf-8") as f:
            f.write(clean_content)

        return TransformationResponse(resultingState=A3EtlProcessState.SANITIZED)
