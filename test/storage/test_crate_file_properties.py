from pathlib import Path

import pytest

from ontobdc.storage.adapter.crate_file_properties import CrateFileProperties


@pytest.fixture(autouse=True)
def fresh_declaration():
    CrateFileProperties._declared = None
    yield
    CrateFileProperties._declared = None


def test_the_ontology_declares_which_properties_the_crate_carries_and_in_which_order() -> None:
    assert CrateFileProperties.declared() == [
        ("name", "FileNameSource", False),
        ("contentSize", "FileSizeSource", False),
        ("dateModified", "ModificationTimeSource", False),
        ("encodingFormat", "MediaTypeSource", True),
        ("dateCreated", "CreationTimeSource", True),
    ]


def test_the_properties_of_a_file_follow_the_declaration(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "photo.png"
    file_path.write_bytes(b"12345")

    properties = CrateFileProperties.of(file_path)

    assert properties is not None
    assert list(properties)[:4] == ["name", "contentSize", "dateModified", "encodingFormat"]
    assert (properties["name"], properties["contentSize"], properties["encodingFormat"]) == ("photo.png", "5", "image/png")
    assert properties["dateModified"].endswith("Z")


def test_an_optional_property_with_no_value_is_left_out(tmp_path: Path) -> None:
    file_path: Path = tmp_path / "no_known_extension.zzzzqq"
    file_path.write_text("x")

    properties = CrateFileProperties.of(file_path)

    assert properties is not None and "encodingFormat" not in properties


def test_a_file_that_is_not_there_has_no_properties(tmp_path: Path) -> None:
    assert CrateFileProperties.of(tmp_path / "gone.txt") is None


def test_a_source_nothing_reads_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(CrateFileProperties._READERS, "FileSizeSource")

    with pytest.raises(ValueError, match="No code reads the value source"):
        CrateFileProperties.declared()
