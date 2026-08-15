"""Regression test: dataset paths with spaces/parentheses must produce a
serializable RDF URI.

Real-world failure this guards against: a Windows OneDrive path like
"OneDrive - Digicorner/Real Estate Brazil (Official)-Obras - Exp
LabSea2025/.../.__infobim__" was concatenated verbatim into
"urn:ontobdc:storage/dataset/<path>" without percent-encoding. rdflib
accepted the URIRef silently but raised on `graph.serialize(format="turtle")`
("... does not look like a valid URI ... Perhaps you wanted to urlencode
it?"), which `hotfix.py`/`check.py` swallowed as a generic
"Failed to hotfix dataset metadata during storage dataset creation." error —
with no indication the real cause was an unescaped path.
"""

from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import (
    _build_expected_dataset_id,
)
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.hotfix import (
    _build_dataset_id,
)

# Mirrors the exact folder shape from the reported failure: spaces, a
# parenthesized segment, and a hyphen-surrounded-by-spaces segment.
_TRICKY_RELATIVE_PARTS = (
    "OneDrive - Digicorner",
    "Real Estate Brazil (Official)-Obras - Exp LabSea2025",
    "Real Estate Brazil - Exp LabSea2025",
    ".__infobim__",
)


def _tricky_paths(tmp_path: Path) -> tuple[Path, Path]:
    root_path = tmp_path
    dataset_path = root_path.joinpath(*_TRICKY_RELATIVE_PARTS)
    dataset_path.mkdir(parents=True)
    return dataset_path, root_path


@pytest.mark.parametrize(
    "build_id",
    [_build_expected_dataset_id, _build_dataset_id],
    ids=["check._build_expected_dataset_id", "hotfix._build_dataset_id"],
)
def test_dataset_id_is_percent_encoded_for_paths_with_spaces_and_parens(tmp_path, build_id):
    dataset_path, root_path = _tricky_paths(tmp_path)

    dataset_id = build_id(dataset_path, root_path)

    assert dataset_id is not None
    assert " " not in dataset_id
    assert "(" not in dataset_id and ")" not in dataset_id
    # The path structure must still be recoverable, just percent-encoded.
    assert "Real%20Estate%20Brazil%20%28Official%29" in dataset_id


@pytest.mark.parametrize(
    "build_id",
    [_build_expected_dataset_id, _build_dataset_id],
    ids=["check._build_expected_dataset_id", "hotfix._build_dataset_id"],
)
def test_dataset_id_serializes_as_turtle_without_raising(tmp_path, build_id):
    dataset_path, root_path = _tricky_paths(tmp_path)
    dataset_id = build_id(dataset_path, root_path)

    graph = Graph()
    graph.add((URIRef(dataset_id), DCTERMS.identifier, Literal(dataset_id)))

    # This is the exact call that raised
    # `... does not look like a valid URI ... Perhaps you wanted to
    # urlencode it?` before the fix.
    serialized = graph.serialize(format="turtle")

    assert dataset_id.replace(" ", "%20") in serialized or "%20" in serialized


def test_dataset_id_round_trips_to_the_same_value_for_the_same_path(tmp_path):
    dataset_path, root_path = _tricky_paths(tmp_path)

    first = _build_expected_dataset_id(dataset_path, root_path)
    second = _build_dataset_id(dataset_path, root_path)

    # check.py and hotfix.py must agree on the same dataset identity for the
    # same path, or "is metadata ready" checks will never match what the
    # hotfix actually wrote.
    assert first == second


def test_dataset_id_is_none_outside_the_root(tmp_path):
    dataset_path = tmp_path / "outside"
    dataset_path.mkdir()
    unrelated_root = tmp_path / "unrelated-root"
    unrelated_root.mkdir()

    assert _build_expected_dataset_id(dataset_path, unrelated_root) is None
    assert _build_dataset_id(dataset_path, unrelated_root) is None
