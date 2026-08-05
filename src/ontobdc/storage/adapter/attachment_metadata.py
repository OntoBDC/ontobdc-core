from pathlib import Path
from typing import Any, Dict, List, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment_error import (
    ContainerAttachError,
    DatasetAttachError,
    InvalidContainerGraphError,
    StorageIndexAttachError,
)
from ontobdc.storage.adapter.attachment_graph import (
    CT,
    OBDC,
    load_graph,
    matching_container_subjects,
    remove_subject,
    required_object,
    rewrite_graph,
    set_single,
)
from ontobdc.storage.adapter.attachment_plan import (
    ATTACH_PLAN_PARAMETER,
    assert_no_storage_conflict,
    is_identity_resolved,
    plan,
    required_resolved_plan,
    uri_mapping,
)
from ontobdc.storage.adapter.attachment_transaction import (
    ensure_attachment_backup,
    write_graphs_transactionally,
)


def attach_container_metadata(context: CliContextPort) -> Dict[str, Any]:
    attachment_plan = required_resolved_plan(context)
    ensure_attachment_backup(
        context,
        attachment_plan,
        ATTACH_PLAN_PARAMETER,
    )
    container_file = Path(attachment_plan["container_file"])
    graph = load_graph(container_file, InvalidContainerGraphError)
    rewritten = rewrite_graph(graph, uri_mapping(attachment_plan))
    target_container = URIRef(
        attachment_plan["target_container_subject"]
    )
    set_single(rewritten, target_container, RDF.type, OBDC.DataContainer)
    set_single(
        rewritten,
        target_container,
        DCTERMS.identifier,
        Literal(attachment_plan["target_container_id"]),
    )
    set_single(
        rewritten,
        target_container,
        PROV.atLocation,
        URIRef(attachment_plan["target_container_location"]),
    )
    for dataset in attachment_plan["datasets"]:
        target_dataset = URIRef(dataset["target_subject"])
        rewritten.add(
            (target_container, OBDC.hasEntityDataset, target_dataset)
        )
        set_single(
            rewritten,
            target_dataset,
            OBDC.belongsToDataContainer,
            target_container,
        )
        set_single(
            rewritten,
            target_dataset,
            PROV.atLocation,
            URIRef(dataset["target_location"]),
        )
    write_graphs_transactionally({container_file: rewritten})
    return {
        "container_file": str(container_file),
        "target_container_id": attachment_plan["target_container_id"],
    }


def is_container_metadata_attached(context: CliContextPort) -> bool:
    attachment_plan = plan(context)
    if attachment_plan is None or not is_identity_resolved(context):
        return False
    try:
        graph = load_graph(
            Path(attachment_plan["container_file"]),
            InvalidContainerGraphError,
        )
        target = URIRef(attachment_plan["target_container_subject"])
        if (target, RDF.type, OBDC.DataContainer) not in graph:
            return False
        if Literal(attachment_plan["target_container_id"]) not in graph.objects(
            target,
            DCTERMS.identifier,
        ):
            return False
        if URIRef(
            attachment_plan["target_container_location"]
        ) not in graph.objects(target, PROV.atLocation):
            return False
        source = URIRef(attachment_plan["source_container_subject"])
        return source == target or not any(graph.predicate_objects(source))
    except ContainerAttachError:
        return False


def attach_datasets(context: CliContextPort) -> Dict[str, Any]:
    attachment_plan = required_resolved_plan(context)
    ensure_attachment_backup(
        context,
        attachment_plan,
        ATTACH_PLAN_PARAMETER,
    )
    payloads: Dict[Path, Graph] = {}
    transformed_datasets: List[Tuple[Dict[str, Any], Graph]] = []
    try:
        for dataset in attachment_plan["datasets"]:
            dataset_file = Path(dataset["file"])
            graph = load_graph(dataset_file, DatasetAttachError)
            rewritten = rewrite_graph(
                graph,
                uri_mapping(attachment_plan),
            )
            target_dataset = URIRef(dataset["target_subject"])
            target_container = URIRef(
                attachment_plan["target_container_subject"]
            )
            set_single(
                rewritten,
                target_dataset,
                RDF.type,
                OBDC.EntityDataset,
            )
            set_single(
                rewritten,
                target_dataset,
                DCTERMS.identifier,
                Literal(dataset["target_id"]),
            )
            set_single(
                rewritten,
                target_dataset,
                PROV.atLocation,
                URIRef(dataset["target_location"]),
            )
            set_single(
                rewritten,
                target_dataset,
                OBDC.belongsToDataContainer,
                target_container,
            )
            set_single(
                rewritten,
                target_dataset,
                OBDC.hasDataEntity,
                URIRef(dataset["target_data_entity"]),
            )
            rewritten.add(
                (
                    URIRef(dataset["target_ontology_subject"]),
                    RDF.type,
                    OWL.Ontology,
                )
            )
            payloads[dataset_file] = rewritten
            transformed_datasets.append((dataset, rewritten))

        container_file = Path(attachment_plan["container_file"])
        container_graph = load_graph(
            container_file,
            InvalidContainerGraphError,
        )
        target_container = URIRef(
            attachment_plan["target_container_subject"]
        )
        for dataset, dataset_graph in transformed_datasets:
            target_dataset = URIRef(dataset["target_subject"])
            remove_subject(container_graph, target_dataset)
            title = required_object(
                dataset_graph,
                target_dataset,
                DCTERMS.title,
                DatasetAttachError,
                "dataset title",
            )
            description = required_object(
                dataset_graph,
                target_dataset,
                DCTERMS.description,
                DatasetAttachError,
                "dataset description",
            )
            container_graph.add(
                (target_container, OBDC.hasEntityDataset, target_dataset)
            )
            container_graph.add(
                (target_dataset, RDF.type, OBDC.EntityDataset)
            )
            container_graph.add(
                (target_dataset, DCTERMS.title, title)
            )
            container_graph.add(
                (target_dataset, DCTERMS.description, description)
            )
            container_graph.add(
                (
                    target_dataset,
                    PROV.atLocation,
                    URIRef(dataset["target_location"]),
                )
            )
            container_graph.add(
                (
                    target_dataset,
                    OBDC.belongsToDataContainer,
                    target_container,
                )
            )
        payloads[container_file] = container_graph
        write_graphs_transactionally(payloads)
    except ContainerAttachError:
        raise
    except Exception as error:
        raise DatasetAttachError(str(error)) from error
    return {
        "dataset_count": len(attachment_plan["datasets"]),
        "container_file": attachment_plan["container_file"],
    }


def is_datasets_attached(context: CliContextPort) -> bool:
    attachment_plan = plan(context)
    if attachment_plan is None or not is_container_metadata_attached(context):
        return False
    try:
        container_graph = load_graph(
            Path(attachment_plan["container_file"]),
            InvalidContainerGraphError,
        )
        target_container = URIRef(
            attachment_plan["target_container_subject"]
        )
        for dataset in attachment_plan["datasets"]:
            dataset_graph = load_graph(
                Path(dataset["file"]),
                DatasetAttachError,
            )
            target_dataset = URIRef(dataset["target_subject"])
            checks = (
                (target_dataset, RDF.type, OBDC.EntityDataset),
                (
                    target_dataset,
                    DCTERMS.identifier,
                    Literal(dataset["target_id"]),
                ),
                (
                    target_dataset,
                    PROV.atLocation,
                    URIRef(dataset["target_location"]),
                ),
                (
                    target_dataset,
                    OBDC.belongsToDataContainer,
                    target_container,
                ),
                (
                    target_dataset,
                    OBDC.hasDataEntity,
                    URIRef(dataset["target_data_entity"]),
                ),
                (
                    URIRef(dataset["target_ontology_subject"]),
                    RDF.type,
                    OWL.Ontology,
                ),
            )
            if any(triple not in dataset_graph for triple in checks):
                return False
            container_checks = (
                (
                    target_container,
                    OBDC.hasEntityDataset,
                    target_dataset,
                ),
                (
                    target_dataset,
                    OBDC.belongsToDataContainer,
                    target_container,
                ),
                (
                    target_dataset,
                    PROV.atLocation,
                    URIRef(dataset["target_location"]),
                ),
            )
            if any(triple not in container_graph for triple in container_checks):
                return False
        return True
    except ContainerAttachError:
        return False


def attach_storage_index(context: CliContextPort) -> Dict[str, Any]:
    attachment_plan = required_resolved_plan(context)
    ensure_attachment_backup(
        context,
        attachment_plan,
        ATTACH_PLAN_PARAMETER,
    )
    assert_no_storage_conflict(attachment_plan)
    try:
        container_graph = load_graph(
            Path(attachment_plan["container_file"]),
            InvalidContainerGraphError,
        )
        storage_file = Path(attachment_plan["storage_file"])
        storage_graph = load_graph(
            storage_file,
            StorageIndexAttachError,
        )
        target = URIRef(attachment_plan["target_container_subject"])
        required_values = {
            predicate: required_object(
                container_graph,
                target,
                predicate,
                StorageIndexAttachError,
                label,
            )
            for predicate, label in (
                (DCTERMS.identifier, "container identifier"),
                (DCTERMS.title, "container title"),
                (CT.creationDate, "container creation date"),
                (CT.description, "container description"),
                (PROV.atLocation, "container location"),
            )
        }
        subjects = matching_container_subjects(
            storage_graph,
            source_subject=URIRef(
                attachment_plan["source_container_subject"]
            ),
            target_subject=target,
            source_id=attachment_plan["source_container_id"],
            target_id=attachment_plan["target_container_id"],
            source_location=attachment_plan["source_container_location"],
            target_location=attachment_plan["target_container_location"],
        )
        for subject in subjects:
            remove_subject(storage_graph, subject)
        storage_graph.add((target, RDF.type, OBDC.DataContainer))
        for predicate, object_value in required_values.items():
            storage_graph.add((target, predicate, object_value))
        write_graphs_transactionally({storage_file: storage_graph})
    except ContainerAttachError:
        raise
    except Exception as error:
        raise StorageIndexAttachError(str(error)) from error
    return {
        "storage_file": attachment_plan["storage_file"],
        "target_container_id": attachment_plan["target_container_id"],
    }


def is_storage_index_attached(context: CliContextPort) -> bool:
    attachment_plan = plan(context)
    if attachment_plan is None or not is_datasets_attached(context):
        return False
    try:
        container_graph = load_graph(
            Path(attachment_plan["container_file"]),
            InvalidContainerGraphError,
        )
        storage_graph = load_graph(
            Path(attachment_plan["storage_file"]),
            StorageIndexAttachError,
        )
        target = URIRef(attachment_plan["target_container_subject"])
        predicates = (
            RDF.type,
            DCTERMS.identifier,
            DCTERMS.title,
            CT.creationDate,
            CT.description,
            PROV.atLocation,
        )
        container_values = sorted(
            (str(predicate), str(object_value))
            for predicate, object_value in container_graph.predicate_objects(
                target
            )
            if predicate in predicates
        )
        storage_values = sorted(
            (str(predicate), str(object_value))
            for predicate, object_value in storage_graph.predicate_objects(
                target
            )
            if predicate in predicates
        )
        if container_values != storage_values:
            return False
        matching_ids = list(
            storage_graph.subjects(
                DCTERMS.identifier,
                Literal(attachment_plan["target_container_id"]),
            )
        )
        matching_locations = list(
            storage_graph.subjects(
                PROV.atLocation,
                URIRef(attachment_plan["target_container_location"]),
            )
        )
        return matching_ids == [target] and matching_locations == [target]
    except ContainerAttachError:
        return False
