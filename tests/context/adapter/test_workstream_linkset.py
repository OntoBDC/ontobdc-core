from rdflib import Literal
from rdflib.namespace import RDF, XSD

from ontobdc.context.adapter.workstream_linkset import (
    LS,
    OBDC,
    WorkStreamResourceLinkset,
)

DIMENSION = "http://example.test/workstream#who"
RESOURCE = "file:///project/team.pdf"


def test_suggested_link_has_browser_compatible_shape_and_status(tmp_path):
    linkset = WorkStreamResourceLinkset(tmp_path, "suggested")
    link = linkset.add(DIMENSION, RESOURCE)

    assert (link, RDF.type, LS.DirectedBinaryLink) in linkset.graph
    assert (link, OBDC.suggestionStatus, OBDC.Proposed) in linkset.graph
    assert (
        linkset.graph.value(link, OBDC.suggestionModifiedAt).datatype
        == XSD.dateTimeStamp
    )
    assert Literal(DIMENSION, datatype=XSD.anyURI) in set(
        linkset.graph.objects(None, LS.uri)
    )
    assert Literal(RESOURCE, datatype=XSD.anyURI) in set(
        linkset.graph.objects(None, LS.uri)
    )
    assert linkset.active_resources(DIMENSION) == {RESOURCE}

    reloaded = WorkStreamResourceLinkset(tmp_path, "suggested")
    assert reloaded.active_resources(DIMENSION) == {RESOURCE}


def test_reject_keeps_history_but_hides_active_suggestion(tmp_path):
    linkset = WorkStreamResourceLinkset(tmp_path, "suggested")
    link = linkset.add(DIMENSION, RESOURCE)
    linkset.reject(DIMENSION, RESOURCE)

    assert (link, RDF.type, LS.DirectedBinaryLink) in linkset.graph
    assert (link, OBDC.suggestionStatus, OBDC.Rejected) in linkset.graph
    assert linkset.active_resources(DIMENSION) == set()


def test_promote_uses_related_linkset_and_never_mutates_it_with_status(tmp_path):
    suggested = WorkStreamResourceLinkset(tmp_path, "suggested")
    suggested.add(DIMENSION, RESOURCE)
    suggested.promote(DIMENSION, RESOURCE)

    related = WorkStreamResourceLinkset(tmp_path, "related")
    assert related.active_resources(DIMENSION) == {RESOURCE}
    assert not list(related.graph.triples((None, OBDC.suggestionStatus, None)))
    assert suggested.active_resources(DIMENSION) == set()


def test_link_iri_is_deterministic(tmp_path):
    first = WorkStreamResourceLinkset(tmp_path, "suggested").add(DIMENSION, RESOURCE)
    second = WorkStreamResourceLinkset(tmp_path, "suggested").add(DIMENSION, RESOURCE)
    assert first == second
