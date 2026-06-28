
import re
import requests
from rdflib.namespace import RDF, OWL
from rdflib import Graph, URIRef, Literal
from typing import Any, Dict, List, Optional
from ontobdc.shared.adapter.util import is_valid_uri
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.a32.domain.port.guardrail import JsonSchemaGuardrailPort


CV = get_ontology_by_prefix('cv')
XSD = get_ontology_by_prefix('xsd')
SH = get_ontology_by_prefix('sh')
SH_OR = URIRef("http://www.w3.org/ns/shacl#or")


class JsonSchemaGuardrailAdapter(JsonSchemaGuardrailPort):

    def __init__(self, schema_uri: str):
        self._schema_uri: str = schema_uri
        self._schema_graph: Graph = Graph()
        self._schema_content: Dict[str, Any] = {}

    @property
    def uri(self) -> str:
        return self._schema_uri

    @property
    def schema(self) -> Dict[str, Any]:
        if not self._schema_content:
            self._schema_content = self._load_schema()
        return self._schema_content

    @property
    def ontology_uri(self) -> str:
        return self._schema_uri.split("#")[0]

    @property
    def shape_id(self) -> str:
        return self._schema_uri.split("#")[1]

    def validate(self, data: Dict[str, Any]) -> None:
        if not data:
            raise ValueError("The data to validate is empty.")

        if not isinstance(data, dict):
            raise ValueError("The data to validate must be a dictionary.")

        schema = self.schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        is_closed = schema.get("additionalProperties") is False
        ignored = schema.get("ignoredProperties", [])

        for prop_name in required:
            if prop_name not in data:
                raise ValueError(f"Required property '{prop_name}' is missing.")

        for prop_name, prop_value in data.items():
            if prop_name in ignored:
                continue
            if prop_name not in properties:
                if is_closed:
                    raise ValueError(
                        f"Additional property '{prop_name}' is not allowed "
                        f"(shape is closed)."
                    )
                continue

            prop_def = properties[prop_name]
            self._validate_property(prop_name, prop_value, prop_def)

    def _validate_property(
        self, name: str, value: Any, prop_def: Dict[str, Any]
    ) -> None:
        expected_type = prop_def.get("type")
        is_array = expected_type == "array"

        if is_array:
            if not isinstance(value, list):
                raise ValueError(
                    f"Property '{name}' must be an array, got {type(value).__name__}."
                )
            items_def = prop_def.get("items", {})

            min_count = prop_def.get("minCount")
            if min_count is not None and len(value) < min_count:
                raise ValueError(
                    f"Property '{name}' must have at least {min_count} items, "
                    f"got {len(value)}."
                )

            max_count = prop_def.get("maxCount")
            if max_count is not None and len(value) > max_count:
                raise ValueError(
                    f"Property '{name}' must have at most {max_count} items, "
                    f"got {len(value)}."
                )

            for i, item in enumerate(value):
                self._validate_scalar(f"{name}[{i}]", item, items_def)
        else:
            self._validate_scalar(name, value, prop_def)

    def _validate_scalar(
        self, name: str, value: Any, prop_def: Dict[str, Any]
    ) -> None:
        expected_type = prop_def.get("type", "string")

        if expected_type == "string":
            if not isinstance(value, str):
                raise ValueError(
                    f"Property '{name}' must be a string, got {type(value).__name__}."
                )
            pattern = prop_def.get("pattern")
            if pattern:
                if not re.match(pattern, value):
                    raise ValueError(
                        f"Property '{name}' value '{value}' does not match "
                        f"pattern '{pattern}'."
                    )
            min_len = prop_def.get("minLength")
            if min_len is not None and len(value) < min_len:
                raise ValueError(
                    f"Property '{name}' must have at least {min_len} characters, "
                    f"got {len(value)}."
                )
        elif expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(
                    f"Property '{name}' must be an integer, got {type(value).__name__}."
                )
        elif expected_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(
                    f"Property '{name}' must be a number, got {type(value).__name__}."
                )
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(
                    f"Property '{name}' must be a boolean, got {type(value).__name__}."
                )

        enum_vals = prop_def.get("enum")
        if enum_vals:
            if value not in enum_vals:
                raise ValueError(
                    f"Property '{name}' value '{value}' is not in allowed values: "
                    f"{enum_vals}."
                )

    def _load_schema(self) -> Dict[str, Any]:
        if not is_valid_uri(self.uri):
            raise ValueError(
                f"The schema URI '{self.uri}' is not valid. "
                "It must be a valid URI with a fragment (#) pointing to a NodeShape."
            )

        try:
            response = requests.get(self.ontology_uri, timeout=10)
            response.raise_for_status()
            content = response.text
        except requests.RequestException as e:
            raise ValueError(
                f"Failed to download the ontology from '{self.ontology_uri}': {e}"
            )

        try:
            self._schema_graph.parse(
                data=content,
                format="turtle",
                publicID=self.ontology_uri,
            )
        except Exception as e:
            raise ValueError(
                f"Failed to parse the ontology from '{self.ontology_uri}': {e}"
            )

        for _, _, obj in self._schema_graph.triples((None, OWL.imports, None)):
            try:
                self._schema_graph.parse(str(obj))
            except Exception as ex_import:
                print(f"Warning: Failed to parse imported ontology {obj}: {ex_import}")

        shape_node = URIRef(self.uri)
        if (shape_node, None, None) not in self._schema_graph:
            raise ValueError(
                f"The shape '{self.shape_id}' was not found in the ontology "
                f"'{self.ontology_uri}'."
            )

        is_node_shape = (shape_node, RDF.type, SH.NodeShape) in self._schema_graph
        if not is_node_shape:
            raise ValueError(
                f"The target node '{self.shape_id}' must be typed as 'sh:NodeShape'."
            )

        json_schema: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        is_closed = self._schema_graph.value(shape_node, SH.closed)
        if is_closed and str(is_closed).lower() == "true":
            json_schema["additionalProperties"] = False

        ignored_props = list(self._schema_graph.objects(shape_node, SH.ignoredProperties))
        if ignored_props:
            json_schema["ignoredProperties"] = [
                self._local_name(p) for p in ignored_props
            ]

        for prop_blank in self._schema_graph.objects(shape_node, SH.property):
            prop_name, prop_def = self._extract_property(prop_blank)
            if prop_name:
                json_schema["properties"][prop_name] = prop_def
                if self._get_int(prop_blank, SH.minCount, 0) >= 1:
                    json_schema["required"].append(prop_name)

        return json_schema

    def _extract_property(self, prop_blank: URIRef) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        path_vals = list(self._schema_graph.objects(prop_blank, SH.path))
        if not path_vals:
            return None, None

        path_uri = path_vals[0]
        prop_name = self._local_name(path_uri)

        prop_def: Dict[str, Any] = {}

        min_count = self._get_int(prop_blank, SH.minCount, None)
        max_count = self._get_int(prop_blank, SH.maxCount, None)
        is_array = max_count is None or max_count > 1

        datatype = self._get_single(prop_blank, SH.datatype)
        node_kind = self._get_single(prop_blank, SH.nodeKind)
        is_multilang = self._has_lang_string_alternative(prop_blank)

        or_node = self._get_single(prop_blank, SH_OR)
        if or_node is not None:
            or_vals = list(self._schema_graph.objects(or_node, None))
            has_lang_string = any(
                str(obj) == str(RDF.langString)
                for obj in or_vals
                if isinstance(obj, URIRef)
            )
            if has_lang_string:
                is_multilang = True

        if node_kind == SH.IRI:
            prop_def["type"] = "string"
        elif is_array:
            prop_def["type"] = "array"
            inner_type = self._rdf_type_to_json_type(datatype) if datatype else "string"
            prop_def["items"] = {"type": inner_type}
            if max_count is not None and max_count > 1:
                prop_def["maxCount"] = max_count
        else:
            prop_def["type"] = self._rdf_type_to_json_type(datatype) if datatype else "string"

        if is_multilang:
            prop_def["multiLanguage"] = True

        if min_count is not None:
            prop_def["minCount"] = min_count

        pattern = self._get_single(prop_blank, SH.pattern)
        if pattern:
            prop_def["pattern"] = str(pattern)

        min_length = self._get_int(prop_blank, SH.minLength, None)
        if min_length is not None:
            prop_def["minLength"] = min_length

        enum_vals = self._get_in_values(prop_blank)
        if enum_vals:
            prop_def["enum"] = enum_vals

        return prop_name, prop_def

    def _extract_property_name(self, path_uri: URIRef) -> str:
        return self._local_name(path_uri)

    def _local_name(self, uri: URIRef) -> str:
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        if "/" in uri_str:
            return uri_str.rsplit("/", 1)[-1]
        return uri_str

    def _rdf_type_to_json_type(self, datatype: Optional[URIRef]) -> str:
        if datatype is None:
            return "string"
        dt_str = str(datatype)
        if dt_str == str(XSD.string) or dt_str.endswith("string"):
            return "string"
        if dt_str == str(XSD.integer) or dt_str.endswith("integer"):
            return "integer"
        if dt_str == str(XSD.boolean) or dt_str.endswith("boolean"):
            return "boolean"
        if dt_str == str(XSD.double) or dt_str == str(XSD.decimal) or dt_str.endswith("double") or dt_str.endswith("decimal"):
            return "number"
        if dt_str == str(XSD.date) or dt_str.endswith("date"):
            return "string"
        if dt_str == str(XSD.dateTime) or dt_str.endswith("dateTime"):
            return "string"
        return "string"

    def _has_lang_string_alternative(self, prop_blank: URIRef) -> bool:
        or_node = self._get_single(prop_blank, SH_OR)
        if or_node is None:
            return False
        for obj in self._schema_graph.objects(or_node, None):
            if isinstance(obj, URIRef) and str(obj) == str(RDF.langString):
                return True
            blank = obj
            dt = self._get_single(blank, SH.datatype)
            if dt and str(dt) == str(RDF.langString):
                return True
        return False

    def _get_single(self, subject: URIRef, predicate) -> Optional[Any]:
        obj = self._schema_graph.value(subject, predicate)
        return obj

    def _get_int(self, subject: URIRef, predicate, default: Optional[int]) -> Optional[int]:
        obj = self._schema_graph.value(subject, predicate)
        if obj is None:
            return default
        try:
            return int(str(obj))
        except (ValueError, TypeError):
            return default

    def _get_in_values(self, prop_blank: URIRef) -> Optional[List[str]]:
        in_node = self._schema_graph.value(prop_blank, SH.in_)
        if in_node is None:
            return None
        members: List[str] = []
        for obj in self._schema_graph.items(in_node):
            if isinstance(obj, Literal):
                members.append(str(obj))
            elif isinstance(obj, URIRef):
                members.append(self._local_name(obj))
        return members if members else None
