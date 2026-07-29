from typing import Any, Dict, List

from ontobdc.shared.adapter.capability import QueryCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class QueryIfcClassAttributesCapability(QueryCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.shared.plugin.capability.query.ifc_class_attributes",
        version="1.0.0",
        name="IFC class attribute query",
        description="Return the IFC attribute names for an informed schema and IFC class using IfcOpenShell schema introspection.",
        author=["TRAE"],
        tags=["shared", "ifc", "ifcopenshell", "schema", "query"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_schema_name": {
                    "type": "string",
                    "required": True,
                    "description": "IFC schema name, such as IFC2X3, IFC4, or IFC4X3_ADD2.",
                },
                "ifc_class_name": {
                    "type": "string",
                    "required": True,
                    "description": "IFC entity class name, such as IfcWall or IfcTask.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_schema_name": {"type": "string"},
                "ifc_class_name": {"type": "string"},
                "ifc_attributes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "is_required": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IFC class attribute query"

    def description(self, lang: str = "en") -> str:
        return "Return the IFC attribute names for an informed schema and IFC class."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import ifcopenshell
        except ImportError as exc:
            raise ValueError("The 'ifcopenshell' package is required to query IFC schema attributes.") from exc

        ifc_schema_name: str = self._get_required_string_input(context=context, parameter_name="ifc_schema_name")
        ifc_class_name: str = self._get_required_string_input(context=context, parameter_name="ifc_class_name")

        schema_definition: Any = ifcopenshell.schema_by_name(ifc_schema_name)
        if schema_definition is None:
            raise ValueError(f"Unsupported IFC schema: {ifc_schema_name}")

        declaration: Any = schema_definition.declaration_by_name(ifc_class_name)
        if declaration is None:
            raise ValueError(
                f"IFC class '{ifc_class_name}' was not found in schema '{ifc_schema_name}'.",
            )

        ifc_attributes: List[Dict[str, Any]] = self._extract_attributes(declaration=declaration)

        return {
            "ifc_schema_name": ifc_schema_name,
            "ifc_class_name": ifc_class_name,
            "ifc_attributes": ifc_attributes,
        }

    def _get_required_string_input(self, context: CliContextPort, parameter_name: str) -> str:
        parameter_value: Any = context.get_parameter_value(parameter_name)
        if not isinstance(parameter_value, str):
            raise ValueError(f"Input '{parameter_name}' must be a string.")

        normalized_value: str = parameter_value.strip()
        if not normalized_value:
            raise ValueError(f"Input '{parameter_name}' cannot be empty.")

        return normalized_value

    def _extract_attributes(self, declaration: Any) -> List[Dict[str, Any]]:
        ifc_attribute_index: Dict[str, Dict[str, Any]] = {}

        for attribute in declaration.all_attributes():
            attribute_name: str = str(attribute.name()).strip()
            is_required: bool = not bool(attribute.optional())
            if attribute_name and attribute_name not in ifc_attribute_index:
                ifc_attribute_index[attribute_name] = {
                    "name": attribute_name,
                    "is_required": is_required,
                }

        return list(ifc_attribute_index.values())
