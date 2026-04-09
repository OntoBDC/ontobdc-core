
from __future__ import annotations

import re
from rdflib import Graph, Literal, URIRef
from typing import Optional, List, Dict, Any, Tuple
from rdflib.namespace import FOAF, OWL, RDF, RDFS, SDO


class KnownUrnDomains:
    _instance: Optional["KnownUrnDomains"] = None

    def __init__(self) -> None:
        self._domains: Dict[str, Dict[str, str]] = self._load_domains()

    @classmethod
    def instance(cls) -> "KnownUrnDomains":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def all(self) -> Dict[str, Dict[str, str]]:
        return self._domains

    def _load_domains(self) -> Dict[str, Dict[str, str]]:
        domains: Dict[str, Dict[str, str]] = {"org.ontobdc": {"nid": "ontobdc-org"}}
        extra = self._read_config_domains()
        for d, v in extra.items():
            if d and d not in domains and isinstance(v, dict) and isinstance(v.get("nid", None), str):
                domains[d] = v

        return domains

    def _read_config_domains(self) -> Dict[str, Dict[str, str]]:
        config = self._read_project_config()

        if not isinstance(config, dict):
            raise ValueError("Project configuration is invalid or missing.")

        known_domains: Optional[Dict[str, Dict[str, str]]] = config.get("known_domain", {})

        if not isinstance(known_domains, dict):
            raise ValueError("Project configuration is invalid or missing known_domains.")
   
        return known_domains

    def _read_project_config(self) -> Dict[str, Any]:
        try:
            from ontobdc.cli import config_data
        except Exception:
            return {}

        cfg = config_data()
        return cfg if isinstance(cfg, dict) else {}


class DirectedAcyclicGraph:
    """
    Wrapper for building an RDF graph (triples) using rdflib.Graph.

    The goal is to make it easier to add RDF triples in the form:
      (subject, predicate, object)
    where the object can be an IRI (URIRef) or a literal (Literal).
    """
    def __init__(self, base_key: str = "org.ontobdc") -> None:
        """
        Args:
            base_key: Base IRI used for Turtle serialization (base URI) and for binding the empty prefix.
        """
        self._known_domains: Dict[str, Dict[str, str]] = KnownUrnDomains.instance().all
        self._base = f"urn:{self.get_dni_from_uri(base_key)[1] if str(self.get_dni_from_uri(base_key)[1]).endswith(':') else (self.get_dni_from_uri(base_key)[1] + ':')}"

        self._graph: Graph = Graph()
        self._graph.bind("", self._base)
        self._graph.bind("obdc_domain", f"{self._base}domain:resource:")
        self._graph.bind("obdc_ldata", f"{self._base}instance:resource:")
        self._graph.bind("obdc_capability", f"{self._base}domain:resource:capability:")
        self._graph.bind("obdc_parameter", f"{self._base}domain:context:strategy:parameter:")
        self._graph.bind("obdc_input", f"{self._base}domain:resource:input:")



        self.add_class(f"{self._base}domain:resource:plan")



        # self._graph.add((URIRef(f"{self._base}ontology"), RDF.type, URIRef(str(OWL))))
        # self._graph.bind("rdf", str(RDF))
        # self._graph.bind("rdfs", str(RDFS))
        # self._graph.bind("owl", str(OWL))
        # self._graph.bind("foaf", str(FOAF))
        # self._graph.bind("sdo", str(SDO))
        # self._graph.add((URIRef(f"{self._base}ontology"), RDF.type, OWL.Ontology))

    def get_dni_from_uri(self, uri: str) -> Optional[Tuple[str, str]]:
        """
        Args:
            uri: URI to extract the domain name from.

        Returns:
            Domain name extracted from the URI if it matches the pattern, otherwise None.
        """
        if not uri:
            return None

        try:
            uri = uri if uri.endswith(".") else (uri + ".")
            for d in self._known_domains.keys():
                if uri.startswith(f"{d}."):
                    return (d, self._known_domains[d].get("nid"))
        except Exception:
            pass

        return None

    def _to_uriref(self, value: str) -> URIRef:
        if value.startswith("urn:") or value.startswith("http://") or value.startswith("https://"):
            return URIRef(value)
        if ":" in value:
            try:
                expanded = self._graph.namespace_manager.expand_curie(value)
                return URIRef(str(expanded))
            except Exception:
                return URIRef(value)
        return URIRef(value)

    def add_class(self, uri: str) -> None:
        self._graph.add((self._to_uriref(uri), RDF.type, OWL.Class))

    def add_individual(self, uri: str, class_uri: str) -> None:
        individual_uri = self._to_uriref(uri)
        self._graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        self._graph.add((individual_uri, RDF.type, self._to_uriref(class_uri)))

    def add_triple(self, s: str, p: str, o: str) -> None:
        """
        Adds an RDF triple whose object is an IRI (URIRef).

        Use this when the object represents a resource (e.g., a capability, an input, an output).

        Args:
            s: Subject IRI.
            p: Predicate IRI.
            o: Object IRI.
        """
        self._graph.add((self._to_uriref(s), self._to_uriref(p), self._to_uriref(o)))

    def add_literal(self, s: str, p: str, o: str) -> None:
        """
        Adds an RDF triple whose object is a literal (Literal).

        Use this when the object is a value (e.g., string/id/description/version).

        Args:
            s: Subject IRI.
            p: Predicate IRI.
            o: Literal value (string).
        """
        self._graph.add((self._to_uriref(s), self._to_uriref(p), Literal(o)))

    def add_property(self, value: Any, property_uri: str) -> None:
        property_ref = self._to_uriref(property_uri)
        self._graph.add((property_ref, RDF.type, OWL.DatatypeProperty))

        if value is None:
            return

        try:
            if isinstance(value, (dict, list, tuple)):
                import json
                lit = Literal(json.dumps(value, ensure_ascii=False))
            else:
                lit = Literal(value)
        except Exception:
            lit = Literal(str(value))

        self._graph.add((property_ref, SDO.value, lit))

    def get_known_domains(self) -> List[Dict[str, str]]:
        return list(self._known_domains.values())

    def to_turtle(self) -> str:
        out = self._graph.serialize(format="turtle")
        return out.decode("utf-8") if isinstance(out, bytes) else str(out)
