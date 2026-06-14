
from rdflib.namespace import DCTERMS
from typing import Any, Dict, List, Optional, Set, Type
from ontobdc.run.domain.port.machine import IntentStatePort
from ontobdc.shared.domain.port.machine import StateEvaluatorPort
from ontobdc.shared.domain.resource.param import ParameterMetadata
from ontobdc.run.domain.port.dag import DagParametersEvaluatorPort
from ontobdc.run.domain.machine.response import IntentScoreResponse
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal
from ontobdc.run.domain.machine.lifecycle import RunIntentResolutionState
from ontobdc.shared.adapter.plugin import CapabilityLoader, ParameterLoader
from ontobdc.shared.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.adapter.ontology import get_ontology_content, get_ontology_by_prefix
from ontobdc.shared.domain.resource.capability import Capability, CapabilityMetadata, QueryCapability


class ContextIntentEvaluatorAdapter(StateEvaluatorPort):
    """
    Adapter to represent the context capability intent resolution process as a IntentStatePort.
    """
    def evaluate(self, context: CliContextPort) -> IntentStatePort:
        """
        Evaluates the given context against the state machine.
        """
        if not context.has_parameter('context_language'):
            return RunIntentResolutionState.EMPTY

        current_state: IntentStatePort = RunIntentResolutionState.LANGUAGE_DEFINED

        if not context.has_parameter('user_intent'):
            return current_state

        current_state = RunIntentResolutionState.INTENDED

        if not context.has_parameter('canonical_intent'):
            return current_state

        current_state = RunIntentResolutionState.CANONICAL

        if not context.has_parameter('intent_score'):
            return current_state

        intent_score = context.get_parameter_value("intent_score")

        if not isinstance(intent_score, (int, float)):
            return current_state

        if intent_score < IntentScoreResponse.INTENT_SCORE_THRESHOLD:
            return RunIntentResolutionState.LOW_CONFIDENCE

        current_state = RunIntentResolutionState.PARSED

        if not context.has_parameter('selected_capability_id'):
            return current_state

        current_state = RunIntentResolutionState.VALIDATED

        if not context.has_parameter('capability_id'):
            return current_state

        dag: DagParametersEvaluatorPort = DagParametersEvaluator(context)

        missing: Optional[Dict[str, Any]] = dag.missing()
        if missing:
            if not dag.evaluate():
                return RunIntentResolutionState.UNREACHABLE

            return RunIntentResolutionState.PLANNED

        return RunIntentResolutionState.FILLED


class DagParametersEvaluator(DagParametersEvaluatorPort):
    """
    Evaluates the parameters for the acyclic graph.
    """

    OBDC: Namespace = get_ontology_by_prefix("obdc")
    FNCT: Namespace = get_ontology_by_prefix("fnct")

    def __init__(self, context: CliContextPort):
        self._context: CliContextPort = context
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._parameter_loader: ParameterLoader = ParameterLoader()
        self._ontology_graph: Graph = get_ontology_content()

        self._graph: Graph = Graph(base="urn:ontobdc:context/dag/")
        self._graph.bind("obdc", self.OBDC)
        self._graph.bind("fnct", self.FNCT)
        self._graph.bind("rdf", RDF)
        self._graph.bind("owl", OWL)

    @property
    def graph(self) -> Graph:
        return self._graph

    def add_query_capability(self, capability: Type[Capability]) -> None:
        """
        Adds the capability to the acyclic graph.
        :param capability: The capability to add.
        """
        if not isinstance(capability, type) or not issubclass(capability, QueryCapability):
            raise ValueError("Capability must be a subclass of QueryCapability")

        capability_uri: URIRef = URIRef(capability.METADATA.id)
        self._graph.add((capability_uri, RDF.type, self.OBDC.QueryCapability))
        self._graph.add((capability_uri, RDFS.subClassOf, self.OBDC.Capability))

        input_properties: Dict[str, Dict[str, Any]] = capability.METADATA.input_schema.get("properties", {})

        for prop_info in input_properties.values():
            parameter_id: Any = prop_info.get("uri")
            if not isinstance(parameter_id, str) or not parameter_id.strip():
                continue

            for parameter_uri in self._ontology_graph.subjects(DCTERMS.identifier, Literal(parameter_id)):
                self._graph.add((capability_uri, self.FNCT.expects, parameter_uri))

        capability_individual: URIRef = URIRef(capability.METADATA.id)
        self._graph.add((capability_individual, RDF.type, OWL.NamedIndividual))
        self._graph.add((capability_individual, RDF.type, capability_uri))

    def get_missing_for_parameter(self, parameter: CliContextStrategyPort) -> List[Type[Capability]]:
        producers: List[Type[Capability]] = []
        parameter_metadata: Optional[ParameterMetadata] = getattr(parameter, "METADATA", None)
        if parameter_metadata is None:
            return producers

        raw_expected_keys: Set[Any] = {
            getattr(parameter_metadata, "name", None),
            getattr(parameter_metadata, "id", None),
        }
        expected_keys: Set[str] = {key for key in raw_expected_keys if isinstance(key, str) and key}

        for capability in self._capability_loader.get_all():
            output_schema: Dict[str, Any] = getattr(capability.METADATA, "output_schema", {}) or {}
            output_properties: Dict[str, Any] = output_schema.get("properties", {})

            for output_key, output_info in output_properties.items():
                if output_key in expected_keys:
                    producers.append(capability)
                    break

                if isinstance(output_info, dict):
                    output_uri = output_info.get("uri")
                    if isinstance(output_uri, str) and output_uri in expected_keys:
                        producers.append(capability)
                        break

        return producers

    def add_parameter(self, parameter: CliContextStrategyPort) -> None:
        """
        Adds the parameter to the acyclic graph.
        :param parameter: The parameter to add.
        """
        parameter_metadata: Optional[ParameterMetadata] = getattr(parameter, "METADATA", None)
        if parameter_metadata is None:
            raise ValueError("Parameter strategy must define METADATA")

        parameter_identifier: Optional[str] = getattr(parameter_metadata, "id", None)
        if not isinstance(parameter_identifier, str) or not parameter_identifier.strip():
            raise ValueError("Parameter strategy metadata must define a non-empty id")

        parameter_class_uri: Optional[URIRef] = next(
            self._ontology_graph.subjects(DCTERMS.identifier, Literal(parameter_identifier)),
            None,
        )
        if not isinstance(parameter_class_uri, URIRef):
            parameter_class_uri = URIRef(parameter_identifier)

        parameter_individual: URIRef = URIRef(parameter_identifier)
        self._graph.add((parameter_individual, RDF.type, OWL.NamedIndividual))
        self._graph.add((parameter_individual, RDF.type, parameter_class_uri))

    def filled(self) -> Dict[str, Any]:
        """
        Returns the filled parameters for the acyclic graph.
        :return: A dictionary of filled parameters. If no filled parameters are found, returns an empty dictionary.
        """
        filled: Dict[str, Any] = {}
        capability: Optional[Type[Capability]] = self._get_target_capability()
        if capability is None:
            return filled

        input_properties: Dict[str, Dict[str, Any]] = capability.METADATA.input_schema.get("properties", {})

        for prop in input_properties.keys():
            value: Any = self._context.get_parameter_value(prop)
            if value is None:
                continue
            filled[prop] = value

        return filled

    def missing(self) -> Dict[str, CliContextStrategyPort]:
        """
        Returns the missing parameters for the acyclic graph.
        :return: A dictionary of missing parameters. If no missing parameters are found, returns an empty dictionary.
        """
        missing: Dict[str, CliContextStrategyPort] = {}
        capability: Optional[Type[Capability]] = self._get_target_capability()
        if capability is None:
            return missing

        input_properties: Dict[str, Dict[str, Any]] = capability.METADATA.input_schema.get("properties", {})

        for prop, prop_info in input_properties.items():
            if not prop_info.get("required", False):
                continue

            value: Any = self._context.get_parameter_value(prop)
            if value is None:
                parameter: Optional[CliContextStrategyPort] = self._parameter_loader.get(prop_info.get("uri"))
                if parameter is not None:
                    missing[prop] = parameter

        return missing

    def evaluate(self) -> bool:
        """
        Evaluates the parameters for the acyclic graph.
        """
        capability: Optional[Type[Capability]] = self._get_target_capability()
        if capability is None:
            return False

        return self._capability_is_resolvable(
            capability=capability,
            visiting=set(),
            capability_memo={},
            parameter_memo={},
        )

    def _get_target_capability(self) -> Optional[Type[Capability]]:
        capability_id: Optional[str] = self._context.get_parameter_value("capability_id")
        if not isinstance(capability_id, str) or not capability_id.strip():
            return None

        return self._capability_loader.get(capability_id)

    def _capability_is_resolvable(
        self,
        capability: Type[Capability],
        visiting: Set[str],
        capability_memo: Dict[str, bool],
        parameter_memo: Dict[str, bool],
    ) -> bool:
        """
        Returns if the capability is resolvable from the current context or by
        recursively resolving producer capabilities for its required inputs.
        """
        capability_metadata: CapabilityMetadata = capability.METADATA
        capability_id: Any = getattr(capability_metadata, "id", None)
        if not isinstance(capability_id, str) or not capability_id.strip():
            return False

        if capability_id in capability_memo:
            return capability_memo[capability_id]

        if capability_id in visiting:
            return False

        visiting.add(capability_id)
        try:
            input_properties: Dict[str, Dict[str, Any]] = capability_metadata.input_schema.get("properties", {})

            for prop_name, prop_info in input_properties.items():
                if not isinstance(prop_info, dict) or not prop_info.get("required", False):
                    continue

                if self._context.get_parameter_value(prop_name) is not None:
                    continue

                parameter_id: Any = prop_info.get("uri")
                if not isinstance(parameter_id, str) or not parameter_id.strip():
                    capability_memo[capability_id] = False
                    return False

                parameter: Optional[CliContextStrategyPort] = self._parameter_loader.get(parameter_id)
                if parameter is None:
                    capability_memo[capability_id] = False
                    return False

                if not self._parameter_is_resolvable(parameter, visiting, capability_memo, parameter_memo):
                    capability_memo[capability_id] = False
                    return False

            capability_memo[capability_id] = True
            return True
        finally:
            visiting.discard(capability_id)

    def _parameter_is_resolvable(
        self,
        parameter: CliContextStrategyPort,
        visiting: Set[str],
        capability_memo: Dict[str, bool],
        parameter_memo: Dict[str, bool],
    ) -> bool:
        """
        Returns if a missing parameter can be satisfied either directly from the
        current context or by at least one producer capability.
        """
        parameter_metadata: Optional[ParameterMetadata] = getattr(parameter, "METADATA", None)
        if parameter_metadata is None:
            return False

        parameter_cache_key: Any = getattr(parameter_metadata, "id", None) or getattr(parameter_metadata, "name", None)
        if not isinstance(parameter_cache_key, str) or not parameter_cache_key.strip():
            return False

        if parameter_cache_key in parameter_memo:
            return parameter_memo[parameter_cache_key]

        parameter_name: Any = getattr(parameter_metadata, "name", None)
        if isinstance(parameter_name, str) and parameter_name.strip():
            if self._context.get_parameter_value(parameter_name) is not None:
                parameter_memo[parameter_cache_key] = True
                return True

        producer_capabilities: List[Type[Capability]] = self.get_missing_for_parameter(parameter)
        if not producer_capabilities:
            parameter_memo[parameter_cache_key] = False
            return False

        result: bool = any(
            self._capability_is_resolvable(
                capability=producer_capability,
                visiting=visiting,
                capability_memo=capability_memo,
                parameter_memo=parameter_memo,
            )
            for producer_capability in producer_capabilities
        )
        parameter_memo[parameter_cache_key] = result
        return result
