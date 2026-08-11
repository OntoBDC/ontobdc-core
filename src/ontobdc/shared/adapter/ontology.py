
from pathlib import Path
from rdflib import Literal
from rdflib.graph import Graph
from rdflib.namespace import Namespace
from typing import Any, Dict, Optional
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.port.ontology import OntologyConfigPort


class OntologyConfigAdapter(OntologyConfigPort):
    """
    Adapter to retrieve and manage ontology configuration and content.
    """
    def __init__(self, config_adapter: ConfigDataPort) -> None:
        self._config_adapter: ConfigDataPort = config_adapter

    def get_ontology_namespace_by_prefix(self, prefix: str) -> Optional[Namespace]:
        """
        Gets an ontology Namespace based on a given prefix.
        """
        ontology_list: Dict[str, Namespace] = {
            "cv": Namespace("http://rdfs.org/resume-rdf/cv.rdfs#"),
            "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
            "peo": Namespace("http://w3id.org/peo#"),
            "sh": Namespace("http://www.w3.org/ns/shacl#"),
            "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
            "obdc": Namespace("http://ontobdc.org/ontology/domain/ns.ttl#"),
            "obdc_code": Namespace("http://ontobdc.org/ontology/domain/code.ttl#"),
            "obdc_test": Namespace("http://ontobdc.org/ontology/domain/test.ttl#"),
            "obdc_view": Namespace("http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#"),
            "olia": Namespace("http://purl.org/olia/olia.owl#"),
            "ct": Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"),
            "fnct": Namespace("http://w3id.org/function/ontology#"),
            "dcat": Namespace("http://www.w3.org/ns/dcat#"),
            "void": Namespace("http://rdfs.org/ns/void#"),
            "schema": Namespace("https://schema.org/"),
            "prov": Namespace("http://www.w3.org/ns/prov#"),
            "ontouml": Namespace("https://w3id.org/ontouml#"),
            "sdo": Namespace("https://w3id.org/okn/o/sd#"),
            "owl": Namespace("http://www.w3.org/2002/07/owl#"),
        }

        return ontology_list.get(prefix, None)

    def get_ontology_path(self, prefix: str, type: str = "ns") -> str:
        """
        Resolves the absolute file path for a requested ontology prefix and type.
        """
        ontology_root: Path = self._config_adapter.ontology_cache
        candidate: Path = ontology_root / prefix

        if candidate.is_file():
            return str(candidate)

        supported_extensions = (".ttl", ".rdf", ".jsonld", ".json-ld", ".owl", ".xml", ".nt", ".n3")
        base_dir: Path = candidate.parent
        base_name: str = candidate.name

        for extension in supported_extensions:
            ontology_file: Path = base_dir / f"{base_name}{extension}"
            if ontology_file.is_file():
                return str(ontology_file)

        ontology_config: Dict[str, Any] = (
            self._config_adapter.all.get("directory", {})
            .get("ontology", {})
            .get(prefix, {})
        )
        absolute_path: Optional[str] = ontology_config.get("absolute_path")
        if absolute_path:
            configured_path: Path = Path(absolute_path)
            if configured_path.is_file():
                return str(configured_path)

            for extension in supported_extensions:
                ontology_file = configured_path / f"{type}{extension}"
                if ontology_file.is_file():
                    return str(ontology_file)

        ontology_type_config: Dict[str, Any] = ontology_config.get(type, {})
        absolute_path = ontology_type_config.get("absolute_path")
        if absolute_path:
            configured_path = Path(absolute_path)
            if configured_path.is_file():
                return str(configured_path)

            for extension in supported_extensions:
                ontology_file = configured_path / f"{type}{extension}"
                if ontology_file.is_file():
                    return str(ontology_file)

        raise FileNotFoundError(f"Ontology file '{prefix}' not found in {ontology_root}")

    def get_ontology_content(self, prefix: str, type: str = "ns") -> Graph:
        """
        Loads and parses the ontology file into an RDF Graph.
        """
        ontology_graph: Graph = Graph()
        ontology_graph.parse(self.get_ontology_path(prefix, type), format="turtle")

        return ontology_graph

    def as_literal(self, value: str) -> Optional[Literal]:
        """
        Safely converts a string value to an RDF Literal.
        """
        if value:
            return Literal(value)

        return None
