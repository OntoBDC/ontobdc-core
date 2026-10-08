from rdflib.namespace import Namespace


#: OntoBDC's own vocabulary: the classes and properties the storage graphs
#: are written with (``obdc:DataStorage``, ``obdc:DataContainer``, ...).
OBDC: Namespace = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")

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
