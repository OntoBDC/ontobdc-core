
from pathlib import Path
from rdflib import Literal
from rdflib.graph import Graph
from typing import Dict, Optional
from rdflib.namespace import Namespace


def get_ontology_by_prefix(prefix: str) -> Optional[Namespace]:
    ontology_list: Dict[str, Namespace] = {
        "cv": Namespace("http://rdfs.org/resume-rdf/cv.rdfs#"),
        "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
        "peo": Namespace("http://w3id.org/peo#"),
        "sh": Namespace("http://www.w3.org/ns/shacl#"),
        "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        "obdc": Namespace("http://ontobdc.org/ontology/domain/ns.ttl#"),
        "olia": Namespace("http://purl.org/olia/olia.owl#"),
        "ct": Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"),
        "fnct": Namespace("http://w3id.org/function/ontology#"),
        "dcat": Namespace("http://www.w3.org/ns/dcat#"),
        "void": Namespace("http://rdfs.org/ns/void#"),
        "schema": Namespace("http://schema.org/"),
        "prov": Namespace("http://www.w3.org/ns/prov#"),
    }

    return ontology_list.get(prefix, None)

def get_ontology_content() -> Graph:
    ONTOLOGY_FILE: Path = Path(__file__).resolve().parents[5] / "docs" / "ontology" / "domain" / "ns.ttl"
    ontology_graph: Graph = Graph()
    ontology_graph.parse(ONTOLOGY_FILE, format="turtle")

    return ontology_graph


def as_literal(value: str) -> Optional[Literal]:
    if value:
        return Literal(value)

    return None