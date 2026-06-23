import json
import os
from typing import Any, Dict, List, Optional, Set, Type

from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.adapter.plugin import CapabilityLoader, ParameterLoader
from ontobdc.run.adapter.evaluator import DagParametersEvaluator
from ontobdc.run.domain.port.dag import DagParametersEvaluatorPort
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.shared.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.resource.capability import Capability, TransformationCapability, CapabilityMetadata


class ResolutionToPlannedCapability(TransformationCapability):
    """
    Capability for planning the selected capability execution.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.planned",
        version="0.1.0",
        name="Intent Planning Resolution",
        description="Plan the selected capability execution.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "intent", "planning", "resolution"],
            "pt": ["dados", "intenção", "planejamento", "resolução"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {},
        },
        output_schema={
            "type": "object",
            "properties": {
                "cli_context": {
                    "type": CliContextPort,
                    "description": "The updated context port with planned execution.",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Intent Planning Resolution",
            "pt": "Resolução de Planejamento de Intenção",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Plan the selected capability execution.",
            "pt": "Planeja a execução da capability selecionada.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to plan the selected capability execution.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the updated context.
        """
        capability_id: str = context.get_parameter_value("selected_capability_id")
        capability: Capability = CapabilityLoader().get(capability_id)
        context.set_parameter_value("capability_id", capability_id)

        dag: DagParametersEvaluatorPort = DagParametersEvaluator(context)
        dag.add_query_capability(capability)
        supporting_capability_ids: Set[str] = self._collect_supporting_capability_ids(
            capability=capability,
            dag=dag,
            visited=set(),
            context=context,
        )

        filled: Dict[str, CliContextStrategyPort] = dag.filled()
        for parameter in filled.values():
            dag.add_parameter(parameter)

        self._dump_supporting_capabilities(sorted(supporting_capability_ids))

        return {
            "cli_context": context,
        }

    def _dump_supporting_capabilities(self, supporting_capability_ids: List[str]) -> None:
        canonicalized_intent_file: str = str(ConfigDataAdapter().config_dir / IntentScoreResponse.CANONICALIZED_INTENT_FILE_NAME)
        if not os.path.exists(canonicalized_intent_file):
            raise RuntimeError(f"Canonicalized intent file not found: {canonicalized_intent_file}")

        with open(canonicalized_intent_file, "r", encoding="utf-8") as canonicalized_handle:
            jsonld_data: Dict[str, Any] = json.load(canonicalized_handle)

        intent_response: IntentScoreResponse = IntentScoreResponse.load_from_jsonld(jsonld_data)
        intent_response.supporting_capabilities = supporting_capability_ids

        with open(canonicalized_intent_file, "w", encoding="utf-8") as canonicalized_handle:
            json.dump(intent_response.serialize(), canonicalized_handle, ensure_ascii=False, indent=4)

    def _collect_supporting_capability_ids(
        self,
        capability: Type[Capability],
        dag: DagParametersEvaluatorPort,
        visited: Set[str],
        context: CliContextPort,
    ) -> Set[str]:
        capability_id: str = capability.METADATA.id
        if capability_id in visited:
            return set()

        visited.add(capability_id)
        supporting_capability_ids: Set[str] = set()
        parameter_loader: ParameterLoader = ParameterLoader()
        input_properties: Dict[str, Dict[str, Any]] = capability.METADATA.input_schema.get("properties", {})

        for prop_name, prop_info in input_properties.items():
            if not prop_info.get("required", False):
                continue

            current_value: Any = context.get_parameter_value(prop_name)
            if current_value is not None:
                continue

            parameter_id: Optional[str] = prop_info.get("uri")
            if not isinstance(parameter_id, str) or not parameter_id.strip():
                continue

            parameter: Optional[CliContextStrategyPort] = parameter_loader.get(parameter_id)
            if parameter is None:
                continue

            producer_capabilities: List[Type[Capability]] = dag.get_missing_for_parameter(parameter)
            for producer_capability in producer_capabilities:
                producer_capability_id: str = producer_capability.METADATA.id
                if producer_capability_id == capability_id:
                    continue

                dag.add_query_capability(producer_capability)
                supporting_capability_ids.add(producer_capability_id)
                supporting_capability_ids.update(
                    self._collect_supporting_capability_ids(
                        capability=producer_capability,
                        dag=dag,
                        visited=visited,
                        context=context,
                    )
                )

        return supporting_capability_ids
