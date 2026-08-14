import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

LS = Namespace("https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#")
OBDC = Namespace("http://ontobdc.org/ontology/domain/ns.ttl#")


class WorkStreamResourceLinkset:
    """Python counterpart of ontobdc-view's WorkStream linkset script."""

    FILES: ClassVar[dict[str, str]] = {
        "related": "WorkStreamResource.ttl",
        "suggested": "WorkStreamSuggested.ttl",
    }
    PREFIXES: ClassVar[dict[str, str]] = {
        "related": "urn:ontobdc:linkset:workstream-resource",
        "suggested": "urn:ontobdc:linkset:workstream-suggested",
    }

    def __init__(self, container_path: Path, kind: str) -> None:
        if kind not in self.FILES:
            raise ValueError(f"Unsupported WorkStream linkset kind: {kind}")
        self.kind = kind
        self.path = (
            Path(container_path).expanduser().resolve()
            / ".__ontobdc__"
            / "linkset"
            / self.FILES[kind]
        )
        self.graph = Graph()
        self.graph.bind("ls", LS)
        self.graph.bind("obdc", OBDC)
        if self.path.is_file():
            self.graph.parse(self.path, format="turtle")

    def active_resources(self, dimension_uri: str) -> set[str]:
        result: set[str] = set()
        for link in self.graph.subjects(RDF.type, LS.DirectedBinaryLink):
            pair = self._pair(link)
            if not pair or pair[0] != dimension_uri:
                continue
            if (
                self.kind == "suggested"
                and self.graph.value(link, OBDC.suggestionStatus) == OBDC.Rejected
            ):
                continue
            result.add(pair[1])
        return result

    def add(self, dimension_uri: str, resource_uri: str) -> URIRef:
        link = self._link_uri(dimension_uri, resource_uri)
        self.graph.add((link, RDF.type, LS.DirectedBinaryLink))
        self._add_element(link, LS.hasFromLinkElement, dimension_uri)
        self._add_element(link, LS.hasToLinkElement, resource_uri)
        if self.kind == "suggested":
            self.graph.set((link, OBDC.suggestionStatus, OBDC.Proposed))
            self.graph.set(
                (
                    link,
                    OBDC.suggestionModifiedAt,
                    Literal(
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        datatype=XSD.dateTimeStamp,
                    ),
                )
            )
        self._save()
        return link

    def reject(self, dimension_uri: str, resource_uri: str) -> None:
        if self.kind != "suggested":
            raise ValueError("Only suggested links have a rejection lifecycle.")
        link = self._link_uri(dimension_uri, resource_uri)
        self.graph.set((link, OBDC.suggestionStatus, OBDC.Rejected))
        self.graph.set(
            (
                link,
                OBDC.suggestionModifiedAt,
                Literal(
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    datatype=XSD.dateTimeStamp,
                ),
            )
        )
        self._save()

    def promote(self, dimension_uri: str, resource_uri: str) -> None:
        WorkStreamResourceLinkset(self.path.parents[2], "related").add(
            dimension_uri, resource_uri
        )
        self.reject(dimension_uri, resource_uri)

    def _link_uri(self, source: str, target: str) -> URIRef:
        digest = hashlib.sha256(f"{source}|{target}".encode()).hexdigest()[:16]
        return URIRef(f"{self.PREFIXES[self.kind]}:{digest}")

    def _add_element(self, link: URIRef, predicate: URIRef, uri: str) -> None:
        element = BNode()
        identifier = BNode()
        self.graph.add((link, predicate, element))
        self.graph.add((element, LS.hasIdentifier, identifier))
        self.graph.add((identifier, RDF.type, LS.URIBasedIdentifier))
        self.graph.add((identifier, LS.uri, Literal(uri, datatype=XSD.anyURI)))

    def _pair(self, link: URIRef) -> tuple[str, str] | None:
        values = []
        for predicate in (LS.hasFromLinkElement, LS.hasToLinkElement):
            element = self.graph.value(link, predicate)
            identifier = self.graph.value(element, LS.hasIdentifier)
            value = self.graph.value(identifier, LS.uri)
            if value is None:
                return None
            values.append(str(value))
        return values[0], values[1]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self.graph.serialize(format="turtle", encoding="utf-8"))
