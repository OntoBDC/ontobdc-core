
import os
import json
from pathlib import Path
from ontobdc.cli import get_config_dir
from typing import Any, Dict, List, Optional
from ontobdc.core.adapter.util import to_pascal_case
from ontobdc.core.domain.resource.entity import Entity
from ontobdc.storage.adapter.icdd import ICDDIndexAdapter
from rdflib import Graph, Namespace, URIRef, Literal, RDF, OWL, XSD


class EntityStorageAdapter:

    INDEX_FILE = "entity.rdf"
    VOAF = Namespace("http://purl.org/vocommons/voaf#")
    DCTERMS = Namespace("http://purl.org/dc/terms/")

    @staticmethod
    def get(unique_name: str) -> Entity:
        return Entity(unique_name)

    @staticmethod
    def create(unique_name: str) -> Entity:
        if EntityStorageAdapter.exists(unique_name):
            raise ValueError(f"Entity {unique_name} already exist")

        entity_path = EntityStorageAdapter.entity_path(unique_name)
        if entity_path is None:
            raise ValueError(f"Invalid entity unique name: {unique_name}")

        entity_path.parent.mkdir(parents=True, exist_ok=True)
        package_name: str = f"urn:entity:{'/'.join(unique_name.split('.')[:-1])}"
        entity_title: str = to_pascal_case(unique_name.split(".")[-1])
        entity_name: str = f"{package_name}/{entity_title}"

        entity_config_graph: Graph = EntityStorageAdapter.entity_config()

        entity_config_graph.bind("owl", OWL)
        entity_config_graph.bind("xsd", XSD)
        entity_config_graph.bind("ct", ICDDIndexAdapter.CT)
        entity_config_graph.bind("voaf", EntityStorageAdapter.VOAF)
        entity_config_graph.bind("dcterms", EntityStorageAdapter.DCTERMS)

        package_ref = URIRef(package_name)
        entity_ref = URIRef(entity_name)

        entity_config_graph.add((package_ref,  RDF.type, EntityStorageAdapter.VOAF.Vocabulary))
        entity_config_graph.add((package_ref,  RDF.type, OWL.Ontology))
        entity_config_graph.add((package_ref,  RDF.type, ICDDIndexAdapter.CT.ContainerDescription))
        entity_config_graph.add((package_ref, OWL.versionInfo, Literal("1.0.0")))
        entity_config_graph.add((package_ref, EntityStorageAdapter.DCTERMS.title, Literal(to_pascal_case('_'.join(unique_name.split('.')[:-1])))))
        entity_config_graph.add((entity_ref,  RDF.type, ICDDIndexAdapter.CT.Linkset))
        entity_config_graph.add((package_ref, ICDDIndexAdapter.CT.containsLinkset, entity_ref))
        entity_config_graph.add((entity_ref, ICDDIndexAdapter.CT.filename, Literal(str(entity_path).split(get_config_dir())[-1].strip('/').strip())))
        entity_config_graph.add((entity_ref, EntityStorageAdapter.DCTERMS.title, Literal(entity_title)))
        entity_config_graph.add((entity_ref, EntityStorageAdapter.DCTERMS.description, Literal(f"An Entity Linked-Ontology Façade (ELOF) for {entity_title}")))
        entity_config_graph.add((entity_ref, ICDDIndexAdapter.CT.containedInContainer, package_ref))

        index_path = os.path.join(get_config_dir(), EntityStorageAdapter.INDEX_FILE)
        entity_config_graph.serialize(destination=index_path, format="pretty-xml")

        context: Dict[str, Any] = {
            "owl": OWL,
            "xsd": XSD,
            "rdf": RDF,
            "ct": ICDDIndexAdapter.CT,
            # "voaf": EntityStorageAdapter.VOAF,
            "dcterms": EntityStorageAdapter.DCTERMS,
        }

        g: Graph = Graph()

        for key, value in context.items():
            g.bind(key, value)

        g.add((entity_ref,  RDF.type, ICDDIndexAdapter.CT.Linkset))
        g.add((entity_ref, EntityStorageAdapter.DCTERMS.title, Literal(entity_title)))
        g.add((entity_ref, EntityStorageAdapter.DCTERMS.description, Literal(f"An Entity Linked-Ontology Façade (ELOF) for {entity_title}")))
        g.add((entity_ref, ICDDIndexAdapter.CT.containedInContainer, package_ref))

        json_context: Dict[str, Dict[str, Any]] = {'@context': {}}
        for key, value in context.items():
            json_context['@context'][key] = str(value)

        json_context['@context']['code'] = '@id'

        with open(entity_path, "w", encoding="utf-8") as f:
            json.dump(json_context, f, indent=2, ensure_ascii=False)

        return EntityStorageAdapter.get(unique_name)

    @staticmethod
    def exists(unique_name: str) -> bool:
        path = EntityStorageAdapter.entity_path(unique_name)
        if path is None:
            return False
        return path.exists()

    @staticmethod
    def entity_path(unique_name: str) -> Optional[Path]:
        config_dir = get_config_dir()
        if config_dir is None:
            return None

        entity_path: str = os.path.join(config_dir, "ontology", "entity")
        parts: List[str] = [p for p in unique_name.split(".") if p]
        if len(parts) == 0:
            return None

        for part in parts:
            part = part.strip().lower()
            entity_path = os.path.join(entity_path, part)

        return Path(entity_path + ".jsonld")

    @staticmethod
    def entity_config() -> Graph:
        config_file_path: str = os.path.join(get_config_dir(), EntityStorageAdapter.INDEX_FILE)
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"Entity index file {config_file_path} not found")

        return Graph().parse(config_file_path, format="xml")

    # @staticmethod
    # def _graph_to_dict(graph: Graph) -> Dict[str, Any]:
    #     """Convert an rdflib Graph to a JSON-LD dictionary."""
    #     jsonld_str = graph.serialize(format="json-ld")
    #     return json.loads(jsonld_str)


class EntityDataStorageAdapter:
    @staticmethod
    def list() -> Dict[str, Any]:
        return EntityStorageAdapter.entity_data()