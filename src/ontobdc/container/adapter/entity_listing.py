import csv
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_rules import EntityFieldRules
from ontobdc.container.domain.exception.entity import EntityFacadeNotFoundError
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerEntities:
    """
    Lists the entities a container holds, dataset by dataset.

    The datasets are the ones the container registers. An entity is a row of
    a data source of its dataset, wherever the dataset keeps it: a CSV
    spreadsheet under ``payload/document`` (one entity per row, identified by
    ``global_id``) or a Turtle file under ``payload/triple`` (one entity per
    typed subject).
    """

    DOCUMENT_DIRECTORY: ClassVar[str] = "document"
    TRIPLE_DIRECTORY: ClassVar[str] = "triple"
    PAYLOAD_DIRECTORY: ClassVar[str] = "payload"
    IDENTIFIER_COLUMN: ClassVar[str] = "global_id"
    NAME_COLUMNS: ClassVar[List[str]] = ["title", "name"]
    ENCODING: ClassVar[str] = "utf-8"

    @classmethod
    def of(cls, container_path: Path) -> List[Dict[str, Any]]:
        """
        One entry per registered dataset: its title, where it is, the
        entity types it declares and the entities its data sources hold.
        """
        container: Path = container_path.expanduser().resolve()
        datasets: List[Dict[str, Any]] = []
        dataset_path: Path
        for dataset_path in cls.distinct_datasets(container):
            metadata: Graph = cls._metadata(dataset_path)
            types: List[str] = cls._entity_types(metadata)
            datasets.append(
                {
                    "title": cls._title(metadata, dataset_path),
                    "path": cls._relative(dataset_path, container),
                    "entity_types": types,
                    "entities": cls._entities(dataset_path, types),
                }
            )

        return datasets

    @staticmethod
    def distinct_datasets(container_path: Path) -> List[Path]:
        """
        The datasets the container registers, once each, in order: a
        container can register the same directory under more than one
        subject, and it is one dataset.
        """
        seen: List[Path] = []
        dataset_path: Path
        for dataset_path in RegisteredDatasets.of(container_path.expanduser().resolve()):
            resolved: Path = dataset_path.resolve()
            if resolved not in seen:
                seen.append(resolved)

        return seen

    @classmethod
    def _metadata(cls, dataset_path: Path) -> Graph:
        graph: Graph = Graph()
        metadata_file: Path = StorageBootstrap.get_dataset_storage_file_path(dataset_path)
        if metadata_file.is_file():
            graph.parse(str(metadata_file), format="turtle")

        return graph

    @classmethod
    def _title(cls, metadata: Graph, dataset_path: Path) -> str:
        for subject in metadata.subjects(RDF.type, OBDC.EntityDataset):
            for title in metadata.objects(subject, DCTERMS.title):
                return str(title)

        return dataset_path.name

    @classmethod
    def _entity_types(cls, metadata: Graph) -> List[str]:
        types: List[str] = []
        subject: Any
        data_entity: Any
        for subject in metadata.subjects(RDF.type, OBDC.EntityDataset):
            for data_entity in metadata.objects(subject, OBDC.hasDataEntity):
                for entity_type in metadata.objects(data_entity, RDF.type):
                    if entity_type != OBDC.DataEntity and str(entity_type) not in types:
                        types.append(str(entity_type))

        return sorted(types)

    @classmethod
    def _entities(cls, dataset_path: Path, types: List[str]) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        default_type: str = cls._local_name(types[0]) if len(types) == 1 else ""
        facade: Optional[EntityFacade] = cls._facade(types)
        entities.extend(cls._triple_entities(dataset_path))
        entities.extend(cls._csv_entities(dataset_path, default_type, facade))
        return entities

    @classmethod
    def facade_of(cls, dataset_path: Path) -> Optional[EntityFacade]:
        """
        The facade of the entity the dataset holds, when it holds one entity
        type and an ontology publishes a facade of it.
        """
        return cls._facade(cls._entity_types(cls._metadata(dataset_path)))

    @staticmethod
    def _facade(types: List[str]) -> Optional[EntityFacade]:
        """
        The facade the ontologies publish for the entity the dataset holds, if
        it holds one entity type and there is a facade of it.
        """
        if len(types) != 1:
            return None

        try:
            return EntityFacadeLocator.of(types[0])
        except EntityFacadeNotFoundError:
            return None

    @classmethod
    def _triple_entities(cls, dataset_path: Path) -> List[Dict[str, Any]]:
        directory: Path = dataset_path / cls.PAYLOAD_DIRECTORY / cls.TRIPLE_DIRECTORY
        entities: List[Dict[str, Any]] = []
        triple_file: Path
        for triple_file in sorted(directory.glob("*.ttl")):
            graph: Graph = Graph()
            graph.parse(str(triple_file), format="turtle")
            subject: Any
            for subject in sorted(set(graph.subjects(RDF.type, None)), key=str):
                if not isinstance(subject, URIRef):
                    continue

                entity_type: Optional[Any] = next(graph.objects(subject, RDF.type), None)
                entities.append(
                    {
                        "global_id": cls._attribute(graph, subject, "globalId")
                        or str(subject),
                        "name": cls._attribute(graph, subject, "name"),
                        "type": cls._local_name(str(entity_type))
                        if entity_type is not None
                        else "",
                        "fields": cls._triple_fields(graph, subject),
                    }
                )

        return entities

    @classmethod
    def _csv_fields(
        cls,
        row: Dict[str, str],
        facade: Optional[EntityFacade],
    ) -> List[Dict[str, Any]]:
        """
        The columns of the row. The ones the facade declares come first, in
        its order, with the names it gives them by language; any other column
        follows, as the data source has it.
        """
        declared: Dict[str, Dict[str, str]] = (
            {field.identifier: field.labels for field in facade.fields}
            if facade is not None
            else {}
        )
        editable: List[str] = (
            [field.identifier for field in facade.fields if EntityFieldRules.is_editable(field)]
            if facade is not None
            else []
        )
        columns: List[str] = [column for column in declared if column in row]
        columns += [column for column in row if column and column not in declared]
        return [
            {
                "name": column,
                "labels": declared.get(column, {}),
                "editable": column in editable,
                "values": [row[column]] if row[column] else [],
            }
            for column in columns
        ]

    @classmethod
    def _triple_fields(cls, graph: Graph, subject: URIRef) -> List[Dict[str, Any]]:
        """
        What the subject says, field by field: the predicate names the field
        and every object it points to is a value.
        """
        values_by_field: Dict[str, List[str]] = {}
        predicate: Any
        value: Any
        for predicate, value in graph.predicate_objects(subject):
            if predicate == RDF.type:
                continue

            values_by_field.setdefault(cls._field_name(str(predicate)), []).append(str(value))

        return [
            {"name": name, "editable": False, "values": sorted(values)}
            for name, values in sorted(values_by_field.items())
        ]

    @classmethod
    def _csv_entities(
        cls,
        dataset_path: Path,
        entity_type: str,
        facade: Optional[EntityFacade],
    ) -> List[Dict[str, Any]]:
        directory: Path = dataset_path / cls.PAYLOAD_DIRECTORY / cls.DOCUMENT_DIRECTORY
        rows_by_id: Dict[str, Dict[str, str]] = {}
        csv_file: Path
        for csv_file in sorted(directory.glob("*.csv")):
            with csv_file.open(encoding=cls.ENCODING, newline="") as handle:
                row: Dict[str, str]
                for row in csv.DictReader(handle):
                    identifier: str = (row.get(cls.IDENTIFIER_COLUMN) or "").strip()
                    if identifier:
                        rows_by_id[identifier] = row

        return [
            {
                "global_id": identifier,
                "name": next(
                    (row[column] for column in cls.NAME_COLUMNS if row.get(column)),
                    "",
                ),
                "type": entity_type,
                "fields": cls._csv_fields(row, facade),
            }
            for identifier, row in rows_by_id.items()
        ]

    @classmethod
    def _attribute(cls, graph: Graph, subject: URIRef, attribute: str) -> str:
        predicate: Any
        value: Any
        for predicate, value in graph.predicate_objects(subject):
            if str(predicate).rsplit("#", 1)[-1].split("_", 1)[0] == attribute:
                return str(value)

        return ""

    @classmethod
    def _field_name(cls, predicate: str) -> str:
        attribute: str = cls._local_name(predicate).split("_", 1)[0]
        return attribute[:1].upper() + attribute[1:]

    @staticmethod
    def _local_name(iri: str) -> str:
        return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    @staticmethod
    def _relative(dataset_path: Path, container_path: Path) -> str:
        try:
            return dataset_path.resolve().relative_to(container_path).as_posix()
        except ValueError:
            return str(dataset_path)
