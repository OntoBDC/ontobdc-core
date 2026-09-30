import re
import json
from typing import Any, ClassVar, Dict, List, Optional, Pattern, Set, Tuple

from rdflib import BNode, Graph, URIRef, Namespace
from rdflib.term import Node
from rdflib.namespace import OWL, RDF, RDFS

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.context.adapter.ontology_term_resolution import (
    OntologyDictionaryTermExtractor,
)


class OntologyKindRepresentationResolver:
    """
    Resolve the representations declared for an ontology term.

    A representation is linked to its kind through CIDOC-CRM P138 or any of
    its sub-properties (such as ``aeco:isVisualRepresentationOf``), declared
    either on the kind (``P138i_has_representation``) or on the
    representation (``P138_represents``). Additionally, non-visual semantic
    bindings declared via DUL Description (``aeco:IfcElementBinding``) are
    also resolved through the inverse pair
    ``aeco:hasIfcElementBinding`` / ``aeco:bindsIfcElementFor``. Both are
    looked up across the ``ns``, ``kind`` and ``kind_representation``
    ontologies of every configured prefix.
    """

    ONTOLOGY_TYPES: ClassVar[Tuple[str, ...]] = ("ns", "kind", "kind_representation")
    CRM: ClassVar[Namespace] = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
    DUL: ClassVar[Namespace] = Namespace(
        "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#"
    )
    AECO: ClassVar[Namespace] = Namespace(
        "http://datacenter.app.br/ontology/domain/aeco/ns.ttl#"
    )

    def __init__(self, graph: Graph) -> None:
        self._graph: Graph = graph

    @classmethod
    def from_configuration(cls) -> "OntologyKindRepresentationResolver":
        ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
            UnsetProjectRootConfigDataAdapter()
        )
        graph: Graph = Graph()
        prefix: str
        for prefix in OntologyDictionaryTermExtractor.ONTOLOGY_PREFIXES:
            type_name: str
            for type_name in cls.ONTOLOGY_TYPES:
                try:
                    graph += ontology_adapter.get_ontology_content(
                        prefix=prefix,
                        type=type_name,
                    )
                except FileNotFoundError:
                    continue
        return cls(graph)

    def representations_of(self, kind: str) -> List[Dict[str, Any]]:
        """Return each representation of ``kind`` with its JSON-LD definition."""
        return [
            {"iri": representation, "json_ld": self._describe(representation)}
            for representation in sorted(self._representation_iris(URIRef(kind)))
        ]

    def _representation_iris(self, kind: URIRef) -> Set[str]:
        representations: Set[str] = set()
        restriction: Node
        representation: Node
        has_representation: Set[Node] = self._with_sub_properties(
            self.CRM.P138i_has_representation
        )
        represents: Set[Node] = self._with_sub_properties(self.CRM.P138_represents)
        has_binding: Set[Node] = self._with_sub_properties(
            self.AECO.hasIfcElementBinding
        )
        binds_for: Set[Node] = self._with_sub_properties(
            self.AECO.bindsIfcElementFor
        )
        for restriction in self._graph.objects(kind, RDFS.subClassOf):
            if not self._restricts(restriction, has_representation | has_binding):
                continue
            for representation in self._graph.objects(restriction, OWL.someValuesFrom):
                representations.add(self._named(representation))
        for restriction in self._graph.subjects(OWL.someValuesFrom, kind):
            if not self._restricts(restriction, represents):
                continue
            for representation in self._graph.subjects(RDFS.subClassOf, restriction):
                representations.add(self._named(representation))
        for restriction in self._graph.subjects(OWL.hasValue, kind):
            if not self._restricts(restriction, binds_for):
                continue
            for representation in self._graph.subjects(RDFS.subClassOf, restriction):
                representations.add(self._named(representation))
        return representations

    def _with_sub_properties(self, root: URIRef) -> Set[Node]:
        return set(self._graph.transitive_subjects(RDFS.subPropertyOf, root))

    def _restricts(self, restriction: Node, on_properties: Set[Node]) -> bool:
        if (restriction, RDF.type, OWL.Restriction) not in self._graph:
            return False
        return any(
            on_property in on_properties
            for on_property in self._graph.objects(restriction, OWL.onProperty)
        )

    def _describe(self, representation: str) -> List[Dict[str, Any]]:
        description: Graph = self._concise_bounded_description(URIRef(representation))
        nodes: Any = json.loads(description.serialize(format="json-ld"))
        if not isinstance(nodes, list) or not nodes:
            raise ValueError(
                f"Representation {representation!r} has no JSON-LD definition."
            )
        return nodes

    def _concise_bounded_description(self, subject: URIRef) -> Graph:
        """Copy every triple describing ``subject``, following blank nodes it owns."""
        description: Graph = Graph()
        visited: Set[Node] = set()
        frontier: List[Node] = [subject]
        while frontier:
            node: Node = frontier.pop()
            if node in visited:
                continue
            visited.add(node)
            predicate: Node
            object_: Node
            for predicate, object_ in self._graph.predicate_objects(node):
                description.add((node, predicate, object_))
                if isinstance(object_, BNode) and object_ not in visited:
                    frontier.append(object_)
        return description

    @staticmethod
    def _named(representation: Node) -> str:
        if not isinstance(representation, URIRef):
            raise ValueError("A kind representation must be a named IRI.")
        return str(representation)


class KindRepresentationSummary:
    """
    Summarize a representation's JSON-LD definition for reading.

    The summary keeps the representation's named superclasses and, for each
    OWL restriction it is a subclass of, the restricted property and its
    filler, shortened to local names. The IFC class the representation
    specializes is reported apart, with its schema, its predefined type when
    restricted, and the names of its associated materials in the identified
    language.
    """

    SUBCLASS_OF: ClassVar[str] = str(RDFS.subClassOf)
    ON_PROPERTY: ClassVar[str] = str(OWL.onProperty)
    FILLERS: ClassVar[Tuple[str, ...]] = (
        str(OWL.someValuesFrom),
        str(OWL.allValuesFrom),
        str(OWL.hasValue),
    )
    IFC_IRI: ClassVar[Pattern[str]] = re.compile(
        r"^https://standards\.buildingsmart\.org/IFC/DEV/(?P<schema>[^/]+)/.*#(?P<name>.+)$"
    )
    AECO_IRI: ClassVar[str] = "http://datacenter.app.br/ontology/domain/aeco/ns.ttl#"
    VISUAL_REPRESENTATION_CLASS: ClassVar[str] = AECO_IRI + "VisualRepresentation"
    ELEMENT_BINDING_CLASS: ClassVar[str] = AECO_IRI + "IfcElementBinding"
    BINDS_PROPERTY: ClassVar[str] = AECO_IRI + "bindsIfcElementFor"
    PREDEFINED_TYPE_PREFIX: ClassVar[str] = "predefinedType_"
    MATERIAL_ASSOCIATIONS: ClassVar[str] = "hasMaterialAssociations"
    RELATING_MATERIAL: ClassVar[str] = "relatingMaterial_IfcRelAssociatesMaterial"
    MATERIAL_NAME: ClassVar[str] = "name_IfcMaterial"

    @classmethod
    def summarize_all(
        cls,
        kind_representations: Dict[str, List[Dict[str, Any]]],
        language: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            term: [
                cls.summarize(
                    term, representation["iri"], representation["json_ld"], language
                )
                for representation in representations
            ]
            for term, representations in kind_representations.items()
        }

    @classmethod
    def summarize(
        cls,
        term: str,
        iri: str,
        json_ld: List[Dict[str, Any]],
        language: str,
    ) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {node["@id"]: node for node in json_ld}
        if iri not in nodes:
            raise ValueError(f"JSON-LD does not describe representation {iri!r}.")
        superclasses: List[str] = []
        ifc_classes: List[Dict[str, str]] = []
        restrictions: List[Dict[str, str]] = []
        predefined_types: List[Dict[str, str]] = []
        materials: List[str] = []
        kind_bindings: List[str] = []
        parent: Dict[str, str]
        classification: Optional[str] = cls._classify(nodes[iri], nodes=nodes)
        for parent in nodes[iri].get(cls.SUBCLASS_OF, []):
            parent_id: str = parent["@id"]
            if parent_id in {cls.VISUAL_REPRESENTATION_CLASS, cls.ELEMENT_BINDING_CLASS}:
                continue
            ifc_match: Optional[re.Match[str]] = cls.IFC_IRI.match(parent_id)
            if parent_id in nodes and cls._is_binding_restriction(
                nodes[parent_id]
            ):
                kind_bindings.extend(cls._binding_targets(nodes[parent_id], nodes))
            elif parent_id in nodes and cls._is_material_association(
                nodes[parent_id]
            ):
                materials.extend(
                    cls._material_names(nodes[parent_id], nodes, language)
                )
            elif parent_id in nodes:
                restriction: Dict[str, str] = cls._restriction(
                    nodes[parent_id], nodes=nodes
                )
                if restriction["property"].startswith(cls.PREDEFINED_TYPE_PREFIX):
                    predefined_types.append(restriction)
                elif restriction["property"] == cls._local_name(cls.BINDS_PROPERTY):
                    kind_bindings.append(restriction["value"])
                else:
                    restrictions.append(restriction)
            elif ifc_match is not None:
                ifc_classes.append(
                    {"class": ifc_match["name"], "schema": ifc_match["schema"]}
                )
            else:
                superclasses.append(cls._local_name(parent_id))
        return {
            "iri": iri,
            "name": cls._local_name(iri),
            "classification": classification,
            "superclasses": sorted(superclasses),
            "restrictions": sorted(
                restrictions,
                key=lambda item: (
                    item["value"] != cls._local_name(term),
                    item["property"],
                    item["value"],
                ),
            ),
            "binds": sorted(set(kind_bindings)),
            "ifc": cls._ifc(iri, ifc_classes, predefined_types, materials),
        }

    @classmethod
    def _ifc(
        cls,
        iri: str,
        ifc_classes: List[Dict[str, str]],
        predefined_types: List[Dict[str, str]],
        materials: List[str],
    ) -> Optional[Dict[str, Any]]:
        if not ifc_classes:
            if predefined_types or materials:
                raise ValueError(
                    f"Representation {iri!r} restricts a predefined type or a "
                    "material without specializing an IFC class."
                )
            return None
        if len(ifc_classes) != 1 or len(predefined_types) > 1:
            raise ValueError(
                f"Representation {iri!r} must specialize one IFC class with at "
                "most one predefined type."
            )
        ifc_class: Dict[str, str] = ifc_classes[0]
        predefined_type: Optional[str] = None
        if predefined_types:
            expected_property: str = cls.PREDEFINED_TYPE_PREFIX + ifc_class["class"]
            if predefined_types[0]["property"] != expected_property:
                raise ValueError(
                    f"Representation {iri!r} restricts "
                    f"{predefined_types[0]['property']} instead of {expected_property}."
                )
            predefined_type = predefined_types[0]["value"]
        return {
            "class": ifc_class["class"],
            "schema": ifc_class["schema"],
            "predefined_type": predefined_type,
            "materials": materials,
        }

    @classmethod
    def _classify(
        cls,
        node: Dict[str, Any],
        *,
        nodes: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        parent: Dict[str, Any]
        for parent in node.get(cls.SUBCLASS_OF, []):
            parent_id: str = parent["@id"]
            if parent_id == cls.VISUAL_REPRESENTATION_CLASS:
                return "visual"
            if parent_id == cls.ELEMENT_BINDING_CLASS:
                return "ifc-binding"
        return None

    @classmethod
    def _is_binding_restriction(cls, node: Dict[str, Any]) -> bool:
        if cls.ON_PROPERTY not in node:
            return False
        return any(
            isinstance(prop, dict)
            and prop.get("@id") == cls.BINDS_PROPERTY
            for prop in node[cls.ON_PROPERTY]
        )

    @classmethod
    def _binding_targets(
        cls,
        restriction: Dict[str, Any],
        nodes: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        targets: List[str] = []
        filler_key: str
        for filler_key in ("http://www.w3.org/2002/07/owl#hasValue",
                           "http://www.w3.org/2002/07/owl#someValuesFrom",
                           "http://www.w3.org/2002/07/owl#allValuesFrom"):
            obj: Any
            for obj in restriction.get(filler_key, []):
                if isinstance(obj, dict) and "@id" in obj:
                    targets.append(cls._local_name(obj["@id"]))
        return targets

    @classmethod
    def _is_material_association(cls, node: Dict[str, Any]) -> bool:
        return cls.ON_PROPERTY in node and any(
            cls.IFC_IRI.match(prop["@id"]) is not None
            and cls._local_name(prop["@id"]) == cls.MATERIAL_ASSOCIATIONS
            for prop in node[cls.ON_PROPERTY]
        )

    @classmethod
    def _material_names(
        cls,
        restriction: Dict[str, Any],
        nodes: Dict[str, Dict[str, Any]],
        language: str,
    ) -> List[str]:
        """Return the names, in ``language``, of the materials a restriction associates."""
        names: List[str] = []
        association: Dict[str, Any]
        for association in cls._objects(restriction, "someValuesFrom", nodes):
            material: Dict[str, Any]
            for material in cls._objects(association, cls.RELATING_MATERIAL, nodes):
                names.append(cls._material_name(material, language))
        if not names:
            raise ValueError(
                f"Material association {restriction['@id']!r} declares no material."
            )
        return names

    @classmethod
    def _objects(
        cls,
        node: Dict[str, Any],
        local_name: str,
        nodes: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        predicate: str
        values: Any
        for predicate, values in node.items():
            if predicate.startswith("@") or cls._local_name(predicate) != local_name:
                continue
            value: Dict[str, Any]
            for value in values:
                if value.get("@id") not in nodes:
                    raise ValueError(
                        f"{local_name} of {node['@id']!r} is not described."
                    )
                objects.append(nodes[value["@id"]])
        return objects

    @classmethod
    def _material_name(cls, material: Dict[str, Any], language: str) -> str:
        primary_language: str = language.strip().lower().split("-", 1)[0]
        literals: List[Dict[str, Any]] = [
            literal
            for predicate, values in material.items()
            if not predicate.startswith("@")
            and cls._local_name(predicate) == cls.MATERIAL_NAME
            for literal in values
        ]
        if not literals:
            raise ValueError(f"Material {material['@id']!r} has no name.")
        localized: List[str] = [
            str(literal["@value"])
            for literal in literals
            if str(literal.get("@language", "")).lower().split("-", 1)[0]
            == primary_language
        ]
        if localized:
            return ", ".join(localized)
        return ", ".join(
            f"{literal['@value']} ({literal.get('@language', 'untagged')})"
            for literal in literals
        )

    @classmethod
    def _restriction(
        cls,
        node: Dict[str, Any],
        *,
        nodes: Optional[Dict[str, Dict[str, Any]]] = None,
        visited: Optional[Set[str]] = None,
    ) -> Dict[str, str]:
        if nodes is None:
            nodes = {}
        if visited is None:
            visited = set()
        properties: List[Dict[str, str]] = node[cls.ON_PROPERTY]
        fillers: List[str] = [key for key in cls.FILLERS if key in node]
        if len(properties) != 1 or len(fillers) != 1 or len(node[fillers[0]]) != 1:
            raise ValueError(
                f"Unsupported OWL restriction in representation: {node['@id']!r}."
            )
        filler: Dict[str, Any] = node[fillers[0]][0]
        filler_value: str
        if "@id" in filler:
            filler_value = cls._resolve_filler_value(
                filler["@id"], nodes=nodes, visited=visited
            )
        else:
            filler_value = cls._format_literal(filler)
        return {
            "property": cls._local_name(properties[0]["@id"]),
            "value": filler_value,
        }

    @classmethod
    def _resolve_filler_value(
        cls,
        target: str,
        *,
        nodes: Dict[str, Dict[str, Any]],
        visited: Set[str],
    ) -> str:
        if target.startswith("_:") and target in nodes and target not in visited:
            visited.add(target)
            target_node: Dict[str, Any] = nodes[target]
            types: List[str] = [
                cls._local_name(t["@id"])
                for t in target_node.get("@type", [])
                if isinstance(t, dict) and "@id" in t
            ]
            header: str = " / ".join(types) if types else cls._local_name(target)
            parts: List[str] = []
            predicate: str
            objects: List[Dict[str, Any]]
            for predicate, objects in target_node.items():
                if predicate in {"@id", "@type"}:
                    continue
                predicate_name: str = cls._local_name(predicate)
                rendered_objects: List[str] = []
                obj: Dict[str, Any]
                for obj in objects:
                    if "@id" in obj:
                        rendered_objects.append(
                            cls._resolve_filler_value(
                                obj["@id"], nodes=nodes, visited=visited
                            )
                        )
                    else:
                        rendered_objects.append(cls._format_literal(obj))
                if len(rendered_objects) == 1:
                    parts.append(f"{predicate_name}: {rendered_objects[0]}")
                else:
                    parts.append(
                        f"{predicate_name}: [{', '.join(rendered_objects)}]"
                    )
            if parts:
                return f"{header} {{ {'; '.join(parts)} }}"
            return header
        return cls._local_name(target)

    @staticmethod
    def _format_literal(literal: Dict[str, Any]) -> str:
        value: str = str(literal["@value"])
        language: Optional[str] = literal.get("@language")
        if language is not None:
            return f'"{value}"@{language}'
        return f'"{value}"'

    @staticmethod
    def _local_name(iri: str) -> str:
        return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
