from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import OBDC, get_container_storage_file_path
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState


class ContainerDatasetsHealthyCapability(TransactionCapability):
    """Run DatasetHealthyCapability for every dataset registered in the container.

    Best-effort, not a hard gate: an individual dataset that stays
    unhealthy (e.g. a facade with no known repair, see
    DatasetHealthyCapability) must not block `ontobdc storage --update` for
    the whole container forever. This state is considered done once the
    pass has *run*, not once every dataset is perfectly healthy — the same
    "ran, regardless of outcome" contract CONTAINER_HTML_VIEW_UPDATED uses
    for `container_html_view_updated`. Per-dataset results are reported,
    not swallowed.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_datasets_healthy"
        ),
        version="1.0.0",
        name="Container Datasets Healthy",
        description=(
            "Repair and validate every dataset registered in the "
            "container, reporting per-dataset health."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "dataset", "update", "health"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_DATASETS_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_DATASETS_HEALTHY.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        from ontobdc.storage.plugin.capability.transformation.dataset_healthy import (
            DatasetHealthyCapability,
        )

        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        container_storage_file_path: Path = get_container_storage_file_path(
            container_path
        )

        dataset_paths: List[Path] = self._resolve_dataset_paths(
            container_storage_file_path, container_path
        )

        previous_dataset_path: Any = context.get_parameter_value("dataset_path")
        results: List[Dict[str, Any]] = []
        try:
            for dataset_path in dataset_paths:
                context.set_parameter_value("dataset_path", str(dataset_path))
                results.append(DatasetHealthyCapability().execute(context))
        finally:
            if previous_dataset_path is None:
                context.delete_parameter("dataset_path")
            else:
                context.set_parameter_value("dataset_path", previous_dataset_path)

        context.set_parameter_value("container_datasets_healthy", True)
        unhealthy: List[str] = [
            str(result["dataset_path"])
            for result in results
            if not result["healthy"]
        ]

        return {
            "resulting_state": (
                ContainerUpdateProcessState.CONTAINER_DATASETS_HEALTHY
            ),
            "container_path": str(container_path),
            "dataset_count": len(results),
            "healthy_dataset_count": len(results) - len(unhealthy),
            "unhealthy_datasets": unhealthy,
            "datasets": results,
        }

    def _resolve_dataset_paths(
        self,
        container_storage_file_path: Path,
        container_path: Path,
    ) -> List[Path]:
        if not container_storage_file_path.is_file():
            return []

        graph: Graph = Graph()
        graph.parse(str(container_storage_file_path), format="turtle")

        container_subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, OBDC.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if len(container_subjects) != 1:
            return []
        container_subject: URIRef = container_subjects[0]

        dataset_subjects: List[URIRef] = [
            subject
            for subject in graph.objects(container_subject, OBDC.hasEntityDataset)
            if isinstance(subject, URIRef)
            and (subject, RDF.type, OBDC.EntityDataset) in graph
        ]

        dataset_paths: List[Path] = []
        for dataset_subject in dataset_subjects:
            locations: List[Any] = list(
                graph.objects(dataset_subject, PROV.atLocation)
            )
            if len(locations) != 1:
                continue
            dataset_paths.append(
                self._location_to_path(str(locations[0]), container_path)
            )
        return dataset_paths

    @staticmethod
    def _location_to_path(location: str, container_path: Path) -> Path:
        parsed = urlparse(location)
        if parsed.scheme == "file":
            return Path(url2pathname(unquote(parsed.path))).expanduser().resolve()

        location_path: Path = Path(location).expanduser()
        if not location_path.is_absolute():
            location_path = container_path / location_path
        return location_path.resolve()
