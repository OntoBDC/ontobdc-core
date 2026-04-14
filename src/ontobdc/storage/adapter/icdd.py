
import os
from uuid import uuid4
from typing import Optional
from lxml import etree as LET
from datetime import datetime, timezone
from rdflib.namespace import RDF, OWL, XSD
from lxml.etree import _Element as LETElement
from rdflib import Graph, Namespace, URIRef, Literal


class ICDDIndexAdapter:
    CT = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Container#")

    def __init__(self, container_path: str):
        self._index_path = os.path.join(container_path, "index.rdf")
        self._index_xml_base: str = None
        self._container_id: str = None
        self._index_graph: Graph = None

    @classmethod
    def create(cls, container_path: str, xml_base: str) -> 'ICDDIndexAdapter':
        if not os.path.isdir(container_path):
            raise ValueError(f"The container path {container_path} is not a directory")

        g = Graph()

        g.bind("ct", cls.CT)
        g.bind("rdfs", Namespace("http://www.w3.org/2000/01/rdf-schema#"))
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        base_ns = f"{xml_base}#"
        g.bind("", Namespace(base_ns))
        g.add((URIRef(xml_base), OWL.imports, URIRef("https://standards.iso.org/iso/21597/-1/ed-1/en/Container")))

        container_id = str(uuid4())
        container_subject = URIRef(f"{container_id}")

        g.add((container_subject, RDF.type, cls.CT.ContainerDescription))
        g.add((container_subject, cls.CT.versionID, Literal("1")))
        g.add((container_subject, cls.CT.versionDescription, Literal("Initial version", lang="en")))
        g.add((container_subject, cls.CT.description, Literal(f"An ICDD container for {xml_base}", lang="en")))

        now_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        g.add((container_subject, cls.CT.creationDate, Literal(now_iso, datatype=XSD.dateTime)))

        container_index: ICDDIndexAdapter = cls(container_path)
        container_index._container_id = container_id
        container_index._index_xml_base = xml_base
        container_index._index_graph = g

        return container_index

    @property
    def container_id(self) -> str:
        if not self._load_index():
            raise ValueError("Container ID not found in RDF file")

        return self._container_id

    @property
    def xml_base(self) -> str:
        return self._index_xml_base

    @property
    def _graph(self) -> Graph:
        if not self._load_index():
            raise ValueError("Failed to load index RDF file")

        return self._index_graph

    def is_loaded(self) -> bool:
        if not isinstance(self._index_graph, Graph):
            return False

        return True

    def serialize(self) -> str:
        rdfxml: str = self._graph.serialize(format="pretty-xml", xml_base=self.xml_base)
        root: LETElement = self._load_index_from_string(rdfxml)

        for rdf_child in root:
            if rdf_child.tag == f"{{{RDF}}}Description":
                for desc_child in rdf_child:
                    if desc_child.tag == f"{{{OWL}}}imports" and 'https://standards.iso.org/iso/21597/-1/ed-1/en/Container' in desc_child.values():
                        owl_element: LETElement = root.makeelement(f"{{{OWL}}}Ontology")
                        owl_element.set(f"{{{RDF}}}about", "")
                        owl_element.insert(0, desc_child)
                        root.replace(rdf_child, owl_element)

            elif rdf_child.tag == f"{{{self._get_namespace('ct')}}}ContainerDescription":
                rdf_child.attrib.pop(f"{{{RDF}}}about", None)
                rdf_child.set(f"{{{RDF}}}ID", self.container_id)

        return self._root_element_to_string(root)

    def save(self) -> None:
        if not self._load_index():
            raise ValueError("Failed to load ICDD index RDF file")

        try:
            rdfxml: str = self.serialize()

            with open(self._index_path, "w", encoding="utf-8") as f:
                f.write(rdfxml)

        except Exception as e:
            raise ValueError(f"Failed to save ICDD index RDF file: {e}")

    def _load_index(self) -> bool:
        if self.is_loaded():
            return True

        self._index_graph = Graph()
        self._index_graph.parse(self._index_path)

        return self.is_loaded()

    def _get_namespace(self, prefix: str) -> Optional[str]:
        for ns in self._graph.namespace_manager.namespaces():
            if ns[0] == prefix:
                return ns[1]

        return None

    def _load_index_from_string(self, rdfxml: str) -> LETElement:
        try:
            parser = LET.XMLParser(remove_blank_text=True)
            root: LETElement = LET.fromstring(rdfxml.encode("utf-8"), parser=parser)
        except Exception:
            parser = LET.XMLParser(remove_blank_text=True, recover=True)
            root: LETElement = LET.fromstring(rdfxml.encode("utf-8"), parser=parser)

        return root

    def _root_element_to_string(self, root: LETElement) -> str:
        LET.indent(root, space="  ")
        return LET.tostring(root, xml_declaration=True, encoding="utf-8", pretty_print=True).decode("utf-8")


class ICDDStorageAdapter:
    def __init__(self, container_path: str):
        self._container_path = container_path
        self._index: ICDDIndexAdapter = None

    @property
    def index(self) -> ICDDIndexAdapter:
        return self._index

    @property
    def container_id(self) -> str:
        if not self._load_container():
            raise ValueError("Container ID not found in RDF file")

        return self.index.container_id

    def _is_loaded(self) -> bool:
        if not isinstance(self.index, ICDDIndexAdapter):
            return False

        if not self.index.is_loaded():
            return False

        return True

    def _load_container(self) -> bool:
        if self._is_loaded():
            return True


        return self._is_loaded()

    @staticmethod
    def create(cls, container_path: str, xml_base: str) -> 'ICDDStorageAdapter':
        if not os.path.isdir(container_path):
            raise ValueError(f"The container path {container_path} is not a directory")

        index_adapter = ICDDIndexAdapter.create(container_path, xml_base)
        container: ICDDStorageAdapter = cls(container_path)
        container._index = index_adapter

        return container

