
from typing import Any, Dict
from rdflib import Graph, URIRef
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.storage.domain.port.repository import DatasetRepositoryPort
from ontobdc.storage.domain.exception.dataset import DatasetIndexNotFoundException
from ontobdc.shared.domain.resource.capability import QueryCapability, CapabilityMetadata


class QueryTaskCapability(QueryCapability):
    """
    Capability to fetch all tasks from a dataset.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.productivity.capability.query.task",
        version="0.1.0",
        name="Query Tasks",
        description="Fetches all tasks from a dataset by looking for the #task-list NamedIndividual.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["productivity", "task", "query", "dataset"],
            "pt": ["produtividade", "tarefa", "consulta", "dataset"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": DatasetRepositoryPort,
                    "uri": "org.ontobdc.domain.storage.capability.incoming.dataset",
                    "required": True,
                    "description": "Dataset repository instance",
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.productivity.task.list": {
                    "type": "object",
                    "description": "The task list NamedIndividual from the dataset",
                },
            },
        },
        raises=[
            {
                "code": "dataset_index_not_found",
                "python_type": DatasetIndexNotFoundException,
                "identifier": "org.ontobdc.domain.storage.exception.dataset.index_not_found",
                "description": "Dataset index.ttl not found in the dataset.",
            }
        ],
    )

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": "Query Tasks",
            "pt": "Consultar Tarefas",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Fetches all tasks from a dataset by looking for the #task-list NamedIndividual.",
            "pt": "Busca todas as tarefas de um dataset procurando pelo NamedIndividual #task-list.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        dataset: DatasetRepositoryPort = context.get_parameter_value("dataset_id")

        index_rdf_path = dataset.path / "index.ttl"

        if not index_rdf_path.exists():
            raise DatasetIndexNotFoundException(f"index.ttl not found at {index_rdf_path}")

        graph = Graph()
        graph.parse(index_rdf_path, format="turtle")

        task_list_uri = URIRef(f"{graph.identifier}#task-list") if graph.identifier else URIRef("#task-list")

        return {
            "org.ontobdc.domain.productivity.task.list": task_list_uri,
        }
