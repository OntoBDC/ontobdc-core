
from typing import Any, Dict
from rdflib import Graph, URIRef
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.storage.domain.port.repository import DatasetRepositoryPort
from ontobdc.storage.domain.exception.dataset import DatasetIndexNotFoundException
from ontobdc.shared.domain.resource.capability import QueryCapability, CapabilityMetadata


class ListAgendaCapability(QueryCapability):
    """
    Capability to fetch the agenda list from a dataset.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.productivity.capability.list.agenda",
        version="0.1.0",
        name="List Agenda",
        description="Fetches the agenda list from a dataset by looking for the #agenda-list NamedIndividual.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["productivity", "agenda", "schedule", "query", "dataset"],
            "pt": ["produtividade", "agenda", "consulta", "dataset"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": DatasetRepositoryPort,
                    "uri": "org.ontobdc.domain.productivity.dataset.repository.incoming",
                    "required": True,
                    "description": "Dataset repository instance",
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.productivity.agenda.list": {
                    "type": "object",
                    "description": "The agenda list NamedIndividual from the dataset",
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
            "en": "List Agenda",
            "pt": "Listar Agenda",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Fetches the agenda list from a dataset by looking for the #agenda-list NamedIndividual.",
            "pt": "Busca a agenda de um dataset procurando pelo NamedIndividual #agenda-list.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        dataset: DatasetRepositoryPort = context.get_parameter_value("dataset_id")

        index_rdf_path = dataset.path / "index.ttl"

        if not index_rdf_path.exists():
            raise DatasetIndexNotFoundException(f"index.ttl not found at {index_rdf_path}")

        graph = Graph()
        graph.parse(index_rdf_path, format="turtle")

        agenda_list_uri = URIRef(f"{graph.identifier}#agenda-list") if graph.identifier else URIRef("#agenda-list")

        return {
            "org.ontobdc.domain.productivity.agenda.list": agenda_list_uri,
        }
