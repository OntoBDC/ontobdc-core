from rdflib.namespace import Namespace


#: OntoBDC's own vocabulary: the classes and properties the storage graphs
#: are written with (``obdc:DataStorage``, ``obdc:DataContainer``, ...).
OBDC: Namespace = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")

#: ISO 21597-1 (Information container for linked document delivery), the
#: standard the containers follow.
CT: Namespace = Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#")
