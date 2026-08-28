import json
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
)
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState

StorageNamespaceBootstrap.initialize()
_OBDC = StorageNamespaceBootstrap.OBDC


METADATA_DIRECTORY = ".__ontobdc__"
ETL_DIRECTORY = "etl"
VIEW_ETL_DIRECTORY = "view"
SURFACE_ETL_DIRECTORY = "surface"
STATE_EXTENSION = "jsonld"

# Per-file rdf:type classification, used to match each file against a
# type-specific display Tile (image/PDF/CSV) or the generic metadata Tile.
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "tif", "tiff"}
_PDF_EXTENSIONS = {"pdf"}
_CSV_EXTENSIONS = {"csv"}


class DataGatheredCapability(TransformationCapability):
    """Materialize presentation input as the DATA_GATHERED JSON-LD state.

    Loads the container's own `container.ttl` into an in-memory graph,
    merges in each registered dataset's own `dataset.ttl`
    (`_add_dataset_triples`), adds an `obdc:FileTree` entity listing the
    container's own files (the RO-Crate payload) for the file/directory
    tree Tile to match against, adds one typed entity per file
    (`obdc:ImageFile`/`PdfFile`/`CsvFile`/`GenericFile` by extension) for
    the per-file display Tiles to match against, and serializes the result
    as the JSON-LD state artifact at the standard ETL path.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "data_gathered"
        ),
        version="1.0.0",
        name="Data Gathered",
        description=(
            "Materialize presentation source data as the DATA_GATHERED "
            "JSON-LD ETL state artifact."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "view",
            "container",
            "publication",
            "data",
            "json-ld",
            "etl",
            "transformation",
        ],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Presentation source data was materialized as the DATA_GATHERED "
                    "JSON-LD ETL state artifact."
                ),
            },
            "debug_entry": {
                "en": (
                    "Materializing presentation source data into the DATA_GATHERED "
                    "JSON-LD ETL state artifact."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.DATA_GATHERED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.DATA_GATHERED.description(lang)

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        container_path = str(
            context.get_parameter_value("container_path") or ""
        ).strip()
        if not container_path:
            raise ValueError("The container path was not resolved.")

        return Path(container_path).expanduser().resolve()

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        return (
            cls._container_path(context)
            / METADATA_DIRECTORY
            / ETL_DIRECTORY
            / VIEW_ETL_DIRECTORY
            / SURFACE_ETL_DIRECTORY
        )

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{SurfaceGenerationProcessState.DATA_GATHERED.value}."
            f"{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort) -> bool:
        try:
            path = self.state_path(context)
            if not path.is_file():
                return False

            value: Any = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(value, (dict, list))
        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return False

    def _build_container_graph(self, context: CliContextPort) -> Graph:
        """Create an in-memory graph holding just the container's own triples."""
        container_file = StorageBootstrap.get_container_storage_file_path(
            self._container_path(context)
        )
        graph = Graph()
        graph.parse(str(container_file), format="turtle")
        return graph

    def _add_surfaceable_declarations(self, graph: Graph) -> None:
        """Declare which entity classes are obdc:SurfaceableEntity —
        SurfaceMatchedCapability's auto-match only includes an entity whose
        rdf:type explicitly carries that marker.

        This graph is built from container.ttl plus this capability's own
        additions only; it never loads ns.ttl or any domain ontology file
        (e.g. type.ttl), so a class's *formal* SurfaceableEntity assertion —
        ns.ttl's own obdc:DataContainer, or WorkStream's in its own
        type.ttl — is invisible here even though it's the source of truth.
        Until this capability loads that TBox data (planned alongside
        re-enabling dataset merging, see _add_dataset_triples above), it
        re-asserts the marker itself for every class it can currently
        produce an instance of.

        `ImageFile`/`PdfFile`/`CsvFile`/`GenericFile` are deliberately NOT
        marked surfaceable: the main Surface must only ever show RO-Crate
        metadata about a container's files, never their real content, so
        auto-matching one inline preview Tile per file entity (thousands, in
        a real container) is the wrong shape entirely regardless of how
        carefully each such Tile defers its own real-file read. Opening a
        file now navigates to the standalone
        `.__ontobdc__/onto-file-viewer.html` page (`onto-file-tree-tile`'s
        job) instead — the one place, and the only moment (an explicit
        click), any real file content is ever read.
        """
        for entity_type in (
            _OBDC.DataContainer,
            _OBDC.FileTree,
        ):
            graph.add((entity_type, RDF.type, _OBDC.SurfaceableEntity))

    def _add_dataset_triples(
        self,
        graph: Graph,
        context: CliContextPort,
    ) -> List[Path]:
        """List the container's datasets and merge each one's triples into `graph`.

        A dataset's own dataset.ttl is the only source of its entities'
        obdc:SurfaceableEntity markers here: this capability never loads an
        external domain ontology file (e.g. type.ttl) to check a class's
        *formal* assertion, so entity.py materializes the marker directly
        into dataset.ttl at creation time (mirroring how it already
        materializes the facade) — see
        ContextEntityCommand._materialize_surfaceable_marker.
        """
        dataset_paths = self._dataset_paths(context)
        for dataset_path in dataset_paths:
            dataset_file = StorageBootstrap.get_dataset_storage_file_path(dataset_path)
            graph.parse(str(dataset_file), format="turtle")
            self._add_dataset_field_values(graph, dataset_path)
        return dataset_paths

    def _add_dataset_field_values(self, graph: Graph, dataset_path: Path) -> None:
        """Materialize each dataset entity's facade field values as literal
        triples on the entity subject (predicate = the field's own
        mapsToProperty, e.g. type:what), read from the dataset's own
        workbook — so a Tile can show them directly from the embedded
        JSON-LD, the same way it already reads title/identifier, without
        fetching/parsing the workbook itself (not feasible client-side for
        a binary format like .xlsx, unlike the CSV Tile).

        Skips a property that already has a value on the entity (title and
        identifier are already set at creation time under different
        predicates than most facade fields map to, but this guards against
        any future overlap too).
        """
        dataset_file = StorageBootstrap.get_dataset_storage_file_path(dataset_path)
        local_graph: Graph = Graph()
        try:
            local_graph.parse(str(dataset_file), format="turtle")
        except Exception:
            return

        dataset_subjects: List[URIRef] = [
            subject
            for subject in local_graph.subjects(RDF.type, _OBDC.EntityDataset)
            if isinstance(subject, URIRef)
        ]
        if len(dataset_subjects) != 1:
            return

        entity_subjects: List[URIRef] = [
            value
            for value in local_graph.objects(dataset_subjects[0], _OBDC.hasDataEntity)
            if isinstance(value, URIRef)
        ]
        if not entity_subjects:
            return

        facade_path: Path = (
            StorageBootstrap.get_ontobdc_directory(dataset_path) / "linkset" / "facade.ttl"
        )
        if not facade_path.is_file():
            return
        facade_graph: Graph = Graph()
        try:
            facade_graph.parse(str(facade_path), format="turtle")
        except Exception:
            return

        for entity_subject in entity_subjects:
            self._add_entity_field_values(
                graph=graph,
                local_graph=local_graph,
                facade_graph=facade_graph,
                dataset_path=dataset_path,
                entity_subject=entity_subject,
            )

    def _add_entity_field_values(
        self,
        *,
        graph: Graph,
        local_graph: Graph,
        facade_graph: Graph,
        dataset_path: Path,
        entity_subject: URIRef,
    ) -> None:
        entity_types: List[URIRef] = [
            value
            for value in local_graph.objects(entity_subject, RDF.type)
            if isinstance(value, URIRef) and value != _OBDC.DataEntity
        ]
        if len(entity_types) != 1:
            return
        entity_type: URIRef = entity_types[0]

        identifiers: List[Any] = list(
            local_graph.objects(entity_subject, DCTERMS.identifier)
        )
        if not identifiers:
            return
        entity_identifier: str = str(identifiers[0]).strip()

        row: Any = self._find_entity_row(dataset_path, entity_type, entity_identifier)
        if row is None:
            return

        # Name / Description are written onto the entity as dcterms:title /
        # dcterms:description at dataset-creation time and stay frozen there —
        # no facade field maps to those predicates, and the facade linkage this
        # capability follows (hasDataEntityFacade) is absent for some entity
        # types anyway. Refresh both straight from the current workbook row so a
        # value edited in the xlsx (e.g. through the Gantt page's inline editor)
        # reaches the generated view instead of the creation-time value.
        row_name: str = str(row.get("Name") or "").strip()
        if row_name:
            graph.set((entity_subject, DCTERMS.title, Literal(row_name)))
        row_description: str = str(row.get("Description") or "").strip()
        if row_description:
            graph.set((entity_subject, DCTERMS.description, Literal(row_description)))

        fields: List[Dict[str, Any]] = self._resolve_facade_fields(
            facade_graph, entity_type
        )
        if not fields:
            return

        for field in fields:
            mapped_property: Any = field.get("mapped_property")
            column_name: str = str(field.get("name") or "").strip()
            if mapped_property is None or not column_name:
                continue
            if (entity_subject, mapped_property, None) in graph:
                continue

            value: str = str(row.get(column_name) or "").strip()
            if not value:
                continue
            graph.add((entity_subject, mapped_property, Literal(value)))

    def _resolve_facade_fields(
        self,
        facade_graph: Graph,
        entity_type: URIRef,
    ) -> List[Dict[str, Any]]:
        facade_subjects: List[URIRef] = [
            obj
            for _, predicate, obj in facade_graph.triples((entity_type, None, None))
            if isinstance(obj, URIRef)
            and self._local_name(predicate) == "hasDataEntityFacade"
        ]
        if not facade_subjects:
            return []

        fields: List[Dict[str, Any]] = []
        for _, predicate, field_subject in facade_graph.triples(
            (facade_subjects[0], None, None)
        ):
            if (
                self._local_name(predicate) != "hasFacadeField"
                or not isinstance(field_subject, URIRef)
            ):
                continue

            identifier: Any = None
            mapped_property: Any = None
            for _, field_predicate, obj in facade_graph.triples(
                (field_subject, None, None)
            ):
                local_name = self._local_name(field_predicate)
                if local_name == "identifier":
                    identifier = obj
                elif local_name == "mapsToProperty" and isinstance(obj, URIRef):
                    mapped_property = obj

            if identifier is None:
                continue
            fields.append(
                {"name": str(identifier).strip(), "mapped_property": mapped_property}
            )
        return fields

    def _find_entity_row(
        self,
        dataset_path: Path,
        entity_type: URIRef,
        entity_identifier: str,
    ) -> Any:
        from ontobdc.context.adapter.dataset_instance import (
            DatasetEntityInstanceRepository,
        )

        try:
            repository = DatasetEntityInstanceRepository(
                dataset_path=str(dataset_path),
                entity=str(entity_type),
            )
            payload: Dict[str, Any] = repository.list_instances()
        except Exception:
            return None

        for instance in list(payload.get("instances") or []):
            if str(instance.get("GlobalId") or "").strip() == entity_identifier:
                return instance
        return None

    @staticmethod
    def _local_name(predicate: Any) -> str:
        predicate_value: str = str(predicate).strip()
        if "#" in predicate_value:
            return predicate_value.rsplit("#", 1)[-1].strip()
        return predicate_value.rstrip("/").rsplit("/", 1)[-1].strip()

    def _dataset_paths(self, context: CliContextPort) -> List[Path]:
        container_path = self._container_path(context)
        return sorted(
            candidate.resolve()
            for candidate in container_path.iterdir()
            if candidate.is_dir()
            and StorageBootstrap.get_dataset_storage_file_path(candidate).is_file()
        )

    def _container_subject(self, graph: Graph) -> URIRef:
        subjects = [
            subject
            for subject in graph.subjects(RDF.type, _OBDC.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError("Expected exactly one DataContainer subject in the container graph.")
        return subjects[0]

    def _add_file_tree_entity(
        self,
        graph: Graph,
        context: CliContextPort,
    ) -> List[str]:
        """Add an `obdc:FileTree` entity listing the container's own files.

        This is the RO-Crate payload — every file the container owns,
        excluding OntoBDC internals and nested datasets (`list_container_resource_paths`,
        already used for publication-descriptor sync). One `obdc:filePath`
        triple per file, so the file/directory tree Tile can rebuild the
        hierarchy client-side from the flat list of relative paths.
        """
        container_subject = self._container_subject(graph)
        file_paths = ContainerDataPackageSynchronizer.list_container_file_paths(self._container_path(context))

        file_tree_subject = URIRef(f"{container_subject}/files")
        graph.add((file_tree_subject, RDF.type, _OBDC.FileTree))
        graph.add((file_tree_subject, DCTERMS.identifier, Literal(str(file_tree_subject))))
        graph.add((file_tree_subject, DCTERMS.title, Literal("Files", lang="en")))
        graph.add((file_tree_subject, DCTERMS.isPartOf, container_subject))
        for file_path in file_paths:
            graph.add((file_tree_subject, _OBDC.filePath, Literal(file_path)))

        return file_paths

    @staticmethod
    def _file_type_uri(extension: str) -> URIRef:
        if extension in _IMAGE_EXTENSIONS:
            return _OBDC.ImageFile
        if extension in _PDF_EXTENSIONS:
            return _OBDC.PdfFile
        if extension in _CSV_EXTENSIONS:
            return _OBDC.CsvFile
        return _OBDC.GenericFile

    def _add_file_entities(
        self,
        graph: Graph,
        context: CliContextPort,
        file_paths: List[str],
    ) -> None:
        """Add one entity per file, typed by extension, for per-file display Tiles.

        Distinct from the aggregate `obdc:FileTree` entity above — this is
        what lets ComponentLoader.match() resolve a specific image/PDF/CSV
        Tile (or the generic metadata Tile as a catch-all) per file, the
        same per-entity matching `data_container_tile.py`/`file_tree_tile.py`
        already rely on.
        """
        container_subject = self._container_subject(graph)
        container_path = self._container_path(context)

        for relative_path in file_paths:
            file_subject = URIRef(f"{container_subject}/files/{quote(relative_path, safe='/')}")
            extension = relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else ""

            graph.add((file_subject, RDF.type, self._file_type_uri(extension)))
            graph.add((file_subject, DCTERMS.identifier, Literal(str(file_subject))))
            graph.add((file_subject, DCTERMS.title, Literal(Path(relative_path).name)))
            graph.add((file_subject, DCTERMS.isPartOf, container_subject))
            graph.add((file_subject, _OBDC.filePath, Literal(relative_path)))
            if extension:
                graph.add((file_subject, DCTERMS.format, Literal(extension)))

            try:
                file_size = (container_path / relative_path).stat().st_size
            except OSError:
                continue
            graph.add((file_subject, _OBDC.fileSize, Literal(file_size)))

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph = self._build_container_graph(context)
        dataset_paths = self._add_dataset_triples(graph, context)
        self._add_surfaceable_declarations(graph)
        file_paths = self._add_file_tree_entity(graph, context)
        self._add_file_entities(graph, context, file_paths)

        payload: Any = json.loads(graph.serialize(format="json-ld"))
        path = self.state_path(context)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "resulting_state": SurfaceGenerationProcessState.DATA_GATHERED,
            "state_path": str(path),
            "file_count": len(file_paths),
            "dataset_count": len(dataset_paths),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
