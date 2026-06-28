
from pathlib import Path
from typing import Any, Dict
from ontobdc.a32.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a32.domain.machine.response import TransformationResponse
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.resource.capability import CapabilityMetadata, TransformationCapability


class TransformationToTypedCapability(TransformationCapability):
    """
    Capability for assigning the parsing shape to a package before parsing.
    """

    MOCK_ETL_SHAPE_URI = "http://ontobdc.org/ontology/social/shp.ttl#JobOfferShape"

    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.typed",
        version="0.1.0",
        name="Data package transformation to Typed",
        description="Assign a parsing shape URI to the data package.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "typed", "shape", "transformation"],
            "pt": ["dados", "tipificado", "shape", "transformacao"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to type.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The typed data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.TYPED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": "Data package transformation to Typed",
            "pt": "Transformacao de pacote de dados para Tipificado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Assign a parsing shape URI to the data package.",
            "pt": "Atribui um shape URI de parsing ao pacote de dados.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        context.set_parameter_value("etl_shape_uri", self.MOCK_ETL_SHAPE_URI)

        return TransformationResponse(resultingState=A3EtlProcessState.TYPED)
