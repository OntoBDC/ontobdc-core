from rdflib.namespace import Namespace


#: OntoBDC's own vocabulary: the classes and properties the storage graphs
#: are written with (``obdc:DataStorage``, ``obdc:DataContainer``, ...).
OBDC: Namespace = Namespace("http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#")

#: The job model: a job, the run of a procedure it points to, the status of the
#: run and the lists that separate the active status from the finished status.
JOB: Namespace = Namespace("http://datacenter.app.br/ontology/tool/ontobdc/core/job.ttl#")

#: The Procedural Knowledge Ontology, the one a procedure is written with.
PKO: Namespace = Namespace("https://w3id.org/pko#")

#: ISO 21597-1 (Information container for linked document delivery), the
#: standard the containers follow.
CT: Namespace = Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#")

#: ISO 21597-1, as the standard publishes it: the namespaces of the container
#: and of the linkset ontologies, which the linksets are written with.
ICDD_CONTAINER: Namespace = Namespace(
    "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
)
ICDD_LINKSET: Namespace = Namespace(
    "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#"
)

#: W3C Linked Data Platform 1.0, the protocol a container is published with
#: over HTTP (``ldp:BasicContainer``, ``ldp:contains``).
LDP: Namespace = Namespace("http://www.w3.org/ns/ldp#")
