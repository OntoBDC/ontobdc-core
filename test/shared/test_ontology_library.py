from pathlib import Path
from typing import Callable, Dict

import pytest
from brasidatacenter import resources
from rdflib import Literal, URIRef
from rdflib.namespace import RDFS

from ontobdc.container.plugin.check.is_dataset_facade_valid.check import (
    main as check_dataset_facade_valid,
)
from ontobdc.container.plugin.check.is_dataset_facade_valid.hotfix import (
    main as hotfix_dataset_facade_valid,
)
from ontobdc.context.adapter.kind_representation import OntologyKindRepresentationResolver
from ontobdc.context.adapter.ontology_term_resolution import OntologyTermResolver
from ontobdc.context.plugin.typification.extension import ExtensionFileTypificationStrategy
from ontobdc.shared.adapter.facade import DataContainerFacade
from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary


BASE: str = resources.ONTOLOGY_BASE_IRI
AECO_CATALOG: str = BASE + "domain/aeco/catalog.ttl"
AECO_KIND: str = BASE + "domain/aeco/taxonomy/kind.ttl"
AECO_ENCODING: str = BASE + "domain/aeco/representation/encoding.ttl"

PREFIXES: str = (
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
)


@pytest.fixture
def ontology_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[Dict[str, str]], None]:
    """
    Replace the installed ontologies by the given files (path under
    ``ontology/`` -> Turtle content).
    """
    root: Path = tmp_path / "ontology"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(resources, "ontology_root", lambda: root)

    def write(files: Dict[str, str]) -> None:
        for relative, content in files.items():
            file_path: Path = root / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(PREFIXES + content, encoding="utf-8")

    return write


class TestBrasidataCenterOntologyLibrary:
    """
    An ontology is found from its IRI alone: the IRI is the package's base
    followed by the path of the ontology's file.
    """

    def test_an_ontology_is_the_file_its_iri_names(self) -> None:
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()

        assert library.path(AECO_KIND) == Path(
            str(resources.ontology_path("domain", "aeco", "taxonomy", "kind.ttl"))
        )

    def test_a_term_iri_names_the_file_of_its_ontology(self) -> None:
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()

        assert library.path(AECO_KIND + "#Parede") == library.path(AECO_KIND)

    def test_every_listed_iri_names_a_package_file(self) -> None:
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        root: Path = Path(str(resources.ontology_root()))

        iris = library.iris()

        assert AECO_CATALOG in iris and AECO_ENCODING in iris
        assert sorted(library.path(iri) for iri in iris) == sorted(
            Path(str(ontology_file)) for ontology_file in resources.iter_ontology_files()
        )
        assert all(library.path(iri).is_relative_to(root) for iri in iris)

    @pytest.mark.parametrize(
        "iri",
        [
            BASE + "domain/aeco/absent.ttl",
            "http://ontobdc.org/ontology/domain/facade.ttl",
        ],
    )
    def test_an_ontology_the_package_lacks_is_an_error_naming_its_iri(self, iri: str) -> None:
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()

        with pytest.raises(FileNotFoundError, match=iri.replace(".", r"\.")):
            library.path(iri)
        with pytest.raises(FileNotFoundError, match=iri.replace(".", r"\.")):
            library.graph(iri)

    def test_the_catalog_with_its_imports_holds_what_the_imports_declare(self) -> None:
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        ifc_step: URIRef = URIRef(AECO_ENCODING + "#IfcStepEncoding")

        assert (ifc_step, None, None) not in library.graph(AECO_CATALOG)
        assert (ifc_step, None, None) in library.graph_with_imports(AECO_CATALOG)

    def test_imports_are_followed_transitively(
        self, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        ontology_tree(
            {
                "a.ttl": f"<{BASE}a.ttl> a owl:Ontology ; owl:imports <{BASE}b.ttl> .",
                "b.ttl": f"<{BASE}b.ttl> a owl:Ontology ; owl:imports <{BASE}c/d.ttl> .",
                "c/d.ttl": f'<{BASE}c/d.ttl#T> rdfs:label "deep" .',
            }
        )

        graph = BrasidataCenterOntologyLibrary().graph_with_imports(BASE + "a.ttl")

        assert (URIRef(BASE + "c/d.ttl#T"), RDFS.label, Literal("deep")) in graph

    def test_an_import_the_package_lacks_is_an_error_naming_it(
        self, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        ontology_tree(
            {"a.ttl": f"<{BASE}a.ttl> a owl:Ontology ; owl:imports <{BASE}missing.ttl> ."}
        )

        with pytest.raises(FileNotFoundError, match="missing"):
            BrasidataCenterOntologyLibrary().graph_with_imports(BASE + "a.ttl")

    def test_the_listed_iris_are_exactly_the_package_files(
        self, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        ontology_tree({"x/y.ttl": "", "z.ttl": ""})

        assert BrasidataCenterOntologyLibrary().iris() == [BASE + "x/y.ttl", BASE + "z.ttl"]


class TestOntologyConsumers:
    """
    What reads an ontology names it by IRI and fails, naming that IRI, when
    the installed package does not have it.
    """

    def test_kinds_are_read_from_the_aeco_catalog_and_its_imports(self) -> None:
        resolver: OntologyKindRepresentationResolver = (
            OntologyKindRepresentationResolver.from_configuration()
        )

        representations = [
            entry["iri"] for entry in resolver.representations_of(AECO_KIND + "#Parede")
        ]

        # The IFC binding is linked through aeco:bindsIfcElementFor, so it is
        # found only when the aeco namespace is the one the catalog binds.
        assert representations == [
            BASE + "domain/aeco/representation/bsi_ifc.ttl#WallIfcBinding",
            BASE + "domain/aeco/representation/geometry.ttl#WallVisual",
        ]

    def test_a_term_is_reported_with_the_ontology_declaring_it(self) -> None:
        resolved = OntologyTermResolver.from_configuration().resolve(
            lemma="parede", language="pt-BR"
        )

        assert resolved["match_type"] == "exact"
        assert (AECO_KIND + "#Parede", AECO_KIND) in [
            (match["iri"], match["ontology"]) for match in resolved["exact_matches"]
        ]

    def test_the_container_facade_names_the_ontology_it_lacks(
        self, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        with pytest.raises(FileNotFoundError, match="facade/data_container.ttl"):
            DataContainerFacade.read()

    def test_typification_names_the_ontology_it_lacks(
        self, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        ExtensionFileTypificationStrategy._type_by_extension.cache_clear()

        with pytest.raises(FileNotFoundError, match="tool/ontobdc/typification.ttl"):
            ExtensionFileTypificationStrategy().evaluate("model.ifc", None)

    def test_the_dataset_facade_check_names_the_shapes_it_lacks(
        self, tmp_path: Path, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        linkset: Path = tmp_path / "payload" / "linkset"
        linkset.mkdir(parents=True)
        (linkset / "dataset_facade.ttl").write_text(
            "<urn:facade> a <http://datacenter.app.br/ontology/tool/ontobdc/facade/ns.ttl#DataEntityFacade> .",
            encoding="utf-8",
        )

        with pytest.raises(FileNotFoundError, match="facade/ns.ttl"):
            check_dataset_facade_valid(dataset_path=str(tmp_path))

    def test_the_dataset_facade_hotfix_names_the_shapes_it_lacks(
        self, tmp_path: Path, ontology_tree: Callable[[Dict[str, str]], None]
    ) -> None:
        with pytest.raises(FileNotFoundError, match="facade/ns.ttl"):
            hotfix_dataset_facade_valid(dataset_path=str(tmp_path))
