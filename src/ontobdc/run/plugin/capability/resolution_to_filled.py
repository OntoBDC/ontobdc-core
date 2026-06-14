from typing import Any, Callable, Dict, List, Optional, Set, Type

from ontobdc.run.adapter.evaluator import DagParametersEvaluator
from ontobdc.shared.adapter.plugin import CapabilityLoader, ParameterLoader
from ontobdc.shared.domain.port.context import CliContextPort, CliContextStrategyPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.shared.domain.resource.capability import Capability, CapabilityExecutor, TransformationCapability, CapabilityMetadata


class ResolutionToFilledCapability(TransformationCapability, LoggerAwarePort, PromptChoiceAwarePort):
    """
    Capability for filling the selected capability execution.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.filled",
        version="0.1.0",
        name="Intent Filling Resolution",
        description="Fill the selected capability execution.",
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

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[Callable] = None

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Intent Filling Resolution",
            "pt": "Resolução de Preenchimento de Intenção",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Fill the selected capability execution.",
            "pt": "Preenche a execução da capability selecionada.",
        }
        return descriptions.get(lang, descriptions["en"])

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: Callable):
        self._prompt_choice = prompt_choice

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        return self._log_strategy

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to fill the selected capability execution.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the updated context.
        """
        capability_id: str = context.get_parameter_value("capability_id") or context.get_parameter_value("selected_capability_id")
        capability: Type[Capability] = CapabilityLoader().get(capability_id)
        context.set_parameter_value("capability_id", capability_id)
        self._fill_capability_inputs(capability=capability, context=context, visited=set())

        return {
            "cli_context": context,
        }

    def _fill_capability_inputs(
        self,
        capability: Type[Capability],
        visited: Set[str],
        context: CliContextPort,
    ) -> None:
        capability_id: str = capability.METADATA.id
        if capability_id in visited:
            return

        visited.add(capability_id)
        try:
            dag: DagParametersEvaluator = DagParametersEvaluator(context)
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
                    raise ValueError(f"Required input '{prop_name}' does not define a valid parameter uri.")

                parameter: Optional[CliContextStrategyPort] = parameter_loader.get(parameter_id)
                if parameter is None:
                    raise ValueError(f"No parameter strategy found for '{parameter_id}'.")

                producer_capabilities: List[Type[Capability]] = dag.get_missing_for_parameter(parameter)
                if not producer_capabilities:
                    raise ValueError(f"No producer capability found for required input '{prop_name}'.")

                producer_capability: Type[Capability] = producer_capabilities[0]
                self._fill_capability_inputs(
                    capability=producer_capability,
                    visited=visited,
                    context=context,
                )

                if context.get_parameter_value(prop_name) is not None:
                    continue

                producer_instance: Capability = producer_capability()
                if isinstance(producer_instance, LoggerAwarePort):
                    producer_instance.set_log_strategy(self._log_strategy)

                if isinstance(producer_instance, PromptChoiceAwarePort):
                    producer_instance.set_prompt_choice(self._prompt_choice)

                producer_result: Dict[str, Any] = CapabilityExecutor.execute(producer_instance, context)
                self._write_capability_outputs_to_context(
                    capability=producer_capability,
                    result=producer_result,
                    context=context,
                )
        finally:
            visited.discard(capability_id)

    def _write_capability_outputs_to_context(
        self,
        capability: Type[Capability],
        result: Dict[str, Any],
        context: CliContextPort,
    ) -> None:
        parameter_loader: ParameterLoader = ParameterLoader()
        output_properties: Dict[str, Dict[str, Any]] = capability.METADATA.output_schema.get("properties", {})

        for output_key, output_value in result.items():
            output_spec: Dict[str, Any] = output_properties.get(output_key, {})
            parameter_uri: Optional[str] = None

            if isinstance(output_key, str) and output_key.startswith("org.ontobdc."):
                parameter_uri = output_key

            output_uri: Optional[str] = output_spec.get("uri")
            if isinstance(output_uri, str) and output_uri.strip():
                parameter_uri = output_uri

            target_key: str = output_key
            if isinstance(parameter_uri, str):
                parameter: Optional[CliContextStrategyPort] = parameter_loader.get(parameter_uri)
                if parameter is not None:
                    target_key = parameter.METADATA.name

            persisted_identifier: Any = getattr(output_value, "id", None)
            if isinstance(persisted_identifier, str) and persisted_identifier.strip():
                context.set_parameter_value(target_key, persisted_identifier)

            context.set_parameter_value(target_key, output_value)
