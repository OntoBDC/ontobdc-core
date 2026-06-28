
from typing import List
from pathlib import Path
from ontobdc.a32.domain.port.machine import (
    EtlProcessStatePort,
    EtlStateEvaluatorPort,
    EtlStateTransitionHandlerPort,
)
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF
from sismic.model.elements import Transition
from ontobdc.shared.adapter.plugin import CapabilityLoader
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.shared.adapter.context import CliContextAdapter
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.a32.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import CapabilityExecutor
from ontobdc.a32.adapter.repository import A3LocalStatechartRepository, TransformableDataPackageRepository

CT = get_ontology_by_prefix("ct")


class StandardA3StateEvaluatorAdapter(EtlStateEvaluatorPort):
    """
    Evaluates the current state of an A3 ETL execution from its context.
    """

    def evaluate(self, context: CliContextPort) -> EtlProcessStatePort:
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")
        package_dir: Path = Path(etl_package_path.path)

        if self._is_federated(package_dir):
            return A3EtlProcessState.FEDERATED

        if (package_dir / "dispatched.jsonld").exists():
            return A3EtlProcessState.DISPATCHED

        if (package_dir / "reasoned.ttl").exists():
            return A3EtlProcessState.REASONED

        if (package_dir / "validated.txt").exists():
            return A3EtlProcessState.VALIDATED

        if (package_dir / "graph.ttl").exists():
            return A3EtlProcessState.TRANSLATED

        if (package_dir / "parsed.json").exists():
            return A3EtlProcessState.PARSED

        if context.has_parameter("etl_shape_uri"):
            return A3EtlProcessState.TYPED

        if (package_dir / "sanitized.txt").exists():
            return A3EtlProcessState.SANITIZED

        if (package_dir / "raw.txt").exists():
            return A3EtlProcessState.RECEIVED

        return A3EtlProcessState.UNDEFINED

    def _is_federated(self, package_dir: Path) -> bool:
        extraction_hash = package_dir.name
        dataset_dir = package_dir.parent
        federated_document_path = dataset_dir / "payload" / "documents" / f"{extraction_hash}.jsonld"
        index_path = dataset_dir / "index.ttl"
        if not federated_document_path.is_file() or not index_path.is_file():
            return False

        graph = Graph()
        try:
            graph.parse(index_path, format="turtle")
        except Exception:
            return False

        ontology_uri = next(graph.subjects(RDF.type, OWL.Ontology), None)
        if not isinstance(ontology_uri, URIRef):
            return False

        document_uri = URIRef(f"{ontology_uri}#{extraction_hash}")
        container_uri = next(graph.subjects(RDF.type, CT.ContainerDescription), None)
        if not isinstance(container_uri, URIRef):
            return False

        return (
            (document_uri, RDF.type, CT.InternalDocument) in graph
            and (container_uri, CT.containsDocument, document_uri) in graph
        )


class SismicA3TransitionHandlerAdapter(EtlStateTransitionHandlerPort):
    def __init__(self, package: str | Path):
        self._package_path: Path = Path(package)
        self._all_transitions: List[Transition] = []
        self._state_evaluator: EtlStateEvaluatorPort = StandardA3StateEvaluatorAdapter()
        self._context: CliContextAdapter = CliContextAdapter(argv=[])
        etl_package_path: LocalRepositoryPort = TransformableDataPackageRepository(self._package_path)
        self._context.set_parameter_value("etl_package_path", etl_package_path)

    @property
    def current_state(self) -> EtlProcessStatePort:
        return self._state_evaluator.evaluate(context=self._context)

    @property
    def transitions(self) -> List[Transition]:
        if not self._all_transitions:
            repository: A3LocalStatechartRepository = A3LocalStatechartRepository()
            statechart = repository.get_statechart()
            self._all_transitions = list(statechart.transitions)

        return self._all_transitions

    @property
    def is_successful(self) -> bool:
        return self.current_state == A3EtlProcessState.FEDERATED

    @property
    def is_unresolvable(self) -> bool:
        return False

    def perform_state_transition(self, to_state: EtlProcessStatePort) -> None:
        capability_id: str = (
            f"org.ontobdc.a3.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"A3 capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def can_transit_to(self, to_state: EtlProcessStatePort) -> bool:
        if self.current_state == to_state:
            return False

        for transition in self.transitions:
            source: A3EtlProcessState = A3EtlProcessState.get_state(transition.source)
            target: A3EtlProcessState = A3EtlProcessState.get_state(transition.target)
            if source == self.current_state and target == to_state:
                return True

        return False

    def validate_state_transition(self, from_state: EtlProcessStatePort, to_state: EtlProcessStatePort) -> bool:
        if from_state == to_state:
            return False

        return self.current_state == to_state

    def system_checks_passed(self) -> bool:
        return True

    def has_error(self) -> bool:
        package_path: Path = self._package_path / "err.json"
        return package_path.exists()
