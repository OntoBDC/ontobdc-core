import mimetypes
from pathlib import Path
from typing import Iterator, Optional

import pytest
from brasidatacenter import resources

from ontobdc.storage.adapter.media_type import MediaTypeResolver


BASE: str = resources.ONTOLOGY_BASE_IRI


@pytest.fixture(autouse=True)
def fresh_declarations() -> Iterator[None]:
    MediaTypeResolver._declared_media_types.cache_clear()
    yield
    MediaTypeResolver._declared_media_types.cache_clear()


def _install_catalog(root: Path, monkeypatch: pytest.MonkeyPatch, encodings: str) -> None:
    """
    Replace the installed ontologies by an AECO catalog importing a schema
    and an encodings ontology holding ``encodings``.
    """
    aeco: Path = root / "domain" / "aeco"
    (aeco / "core").mkdir(parents=True)
    (aeco / "representation").mkdir()
    prefixes: str = (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        f"@prefix aeco: <{BASE}domain/aeco/core/schema.ttl#> .\n"
    )
    (aeco / "catalog.ttl").write_text(
        prefixes
        + f"<{BASE}domain/aeco/catalog.ttl> a owl:Ontology ; owl:imports "
        f"<{BASE}domain/aeco/representation/encoding.ttl> .\n",
        encoding="utf-8",
    )
    (aeco / "representation" / "encoding.ttl").write_text(
        prefixes + f"<{BASE}domain/aeco/representation/encoding.ttl> a owl:Ontology .\n" + encodings,
        encoding="utf-8",
    )
    monkeypatch.setattr(resources, "ontology_root", lambda: root)


class TestMediaTypeResolverWithTheInstalledOntology:
    @pytest.mark.parametrize(
        ("file_name", "media_type"),
        [
            ("model.ifc", "application/x-step"),
            ("MODEL.IFC", "application/x-step"),
            ("plan.dxf", "image/vnd.dxf"),
        ],
    )
    def test_the_domain_formats_take_the_type_the_ontology_declares(
        self, file_name: str, media_type: str
    ) -> None:
        assert MediaTypeResolver.of(file_name) == media_type

    def test_a_compressed_domain_file_keeps_its_type_and_reports_the_compression(self) -> None:
        assert MediaTypeResolver.guess("model.ifc.gz") == ("application/x-step", "gzip")

    @pytest.mark.parametrize(
        ("file_name", "media_type"),
        [
            ("table.csv", "text/csv"),
            ("report.pdf", "application/pdf"),
            ("settings.yaml", mimetypes.MimeTypes().guess_type("settings.yaml")[0]),
        ],
    )
    def test_other_formats_take_the_type_built_into_python(
        self, file_name: str, media_type: Optional[str]
    ) -> None:
        assert MediaTypeResolver.of(file_name) == media_type

    @pytest.mark.parametrize("file_name", ["data.unknownext", "README"])
    def test_a_format_neither_knows_has_no_type(self, file_name: str) -> None:
        assert MediaTypeResolver.guess(file_name) == (None, None)


class TestMediaTypeResolverReadsTheOntology:
    def test_the_type_comes_from_the_ontology_not_from_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_catalog(
            tmp_path,
            monkeypatch,
            "<urn:ifc> a aeco:FileEncoding ; aeco:fileExtension \"ifc\" ; aeco:mediaType \"model/x-test-ifc\" .\n"
            "<urn:csv> a aeco:FileEncoding ; aeco:fileExtension \"CSV\" ; aeco:mediaType \"text/x-test-csv\" .\n",
        )

        assert MediaTypeResolver.of("model.ifc") == "model/x-test-ifc"
        assert MediaTypeResolver.of("table.csv") == "text/x-test-csv"
        assert MediaTypeResolver.of("plan.dxf") is None

    def test_an_encoding_without_a_media_type_declares_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_catalog(
            tmp_path,
            monkeypatch,
            "<urn:ifc> a aeco:FileEncoding ; aeco:fileExtension \"ifc\" .\n",
        )

        assert MediaTypeResolver.of("model.ifc") is None

    def test_without_the_catalog_no_type_can_be_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(resources, "ontology_root", lambda: tmp_path)

        with pytest.raises(FileNotFoundError, match="aeco/catalog.ttl"):
            MediaTypeResolver.of("table.csv")
