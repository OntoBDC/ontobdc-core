
import os
import json
from ontobdc.cli import get_config_dir
from typing import Any, Dict, Optional, Type
from ontobdc.shared.adapter.plugin import CapabilityLoader
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.shared.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.run.domain.exception.intent import UserCanceledCapabilitySelectionException
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata, Capability


class ResolutionToValidatedCapability(TransformationCapability, LoggerAwarePort, PromptChoiceAwarePort):
    """
    Capability for validating the parsed user intent.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.validated",
        version="0.1.0",
        name="Intent Validation Resolution",
        description="Validate the parsed user intent.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "intent", "validation", "resolution"],
            "pt": ["dados", "intenção", "validação", "resolução"],
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
                    "description": "The updated context port with validated intent.",
                },
            },
        },
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[callable] = None

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Intent Validation Resolution",
            "pt": "Resolução de Validação de Intenção",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Validate the parsed user intent.",
            "pt": "Valida a intenção interpretada do usuário.",
        }
        return descriptions.get(lang, descriptions["en"])

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: callable):
        self._prompt_choice = prompt_choice

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        """
        Returns the log strategy container.
        """
        return self._log_strategy

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to validate the parsed user intent.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the updated context.
        """
        if self._prompt_choice is None:
            raise RuntimeError("Prompt choice function is not configured.")

        # Read the canonicalized intent file
        parsed_intent_file: str = os.path.join(get_config_dir(), IntentScoreResponse.CANONICALIZED_INTENT_FILE_NAME)
        if not os.path.exists(parsed_intent_file):
            raise RuntimeError(f"Canonicalized intent file not found: {parsed_intent_file}")

        with open(parsed_intent_file, "r") as f:
            jsonld_data = json.load(f)

        # Load intent response
        intent_response = IntentScoreResponse.load_from_jsonld(jsonld_data)

        # Check for matching capabilities
        if not intent_response.matching_capabilities:
            raise RuntimeError("No matching capabilities found.")

        # Load all capabilities and filter matching ones
        all_capabilities = CapabilityLoader().get_all("capability")
        matching_capabilities: list[Type[Capability]] = []

        for capability_id in intent_response.matching_capabilities:
            for capability in all_capabilities:
                if capability.METADATA.id == capability_id:
                    matching_capabilities.append(capability)
                    break

        if not matching_capabilities:
            raise RuntimeError("Matching capabilities not found in the loader.")

        # Normalizar língua (pt-BR -> pt)
        normalized_lang = context.language
        if normalized_lang and "-" in normalized_lang:
            normalized_lang = normalized_lang.split("-")[0]

        # Prepare choice options
        prompts = {
            "en": "I found some possible capabilities. Which one do you want to use?",
            "pt": "Encontrei algumas capabilities possíveis. Qual você quer usar?",
        }
        prompt_text = prompts.get(normalized_lang, prompts["en"])
        
        choice_options = []
        for capability in matching_capabilities:
            capability_instance = capability()
            label = capability_instance.label(normalized_lang)
            description = capability_instance.description(normalized_lang)
            choice_options.append(f"{label}")

        # Show prompt choice
        selected_text: str = self._prompt_choice(prompt_text, choice_options, language=normalized_lang)
        selected_index: int = choice_options.index(selected_text)

        # Handle user selection
        if selected_index is None or selected_index < 0:
            error_messages = {
                "en": "Could not understand your request. Please try again.",
                "pt": "Não foi possível entender sua solicitação. Por favor, tente novamente.",
            }
            error_message = error_messages.get(normalized_lang, error_messages["en"])
            raise UserCanceledCapabilitySelectionException(error_message)

        # Get the selected capability
        selected_capability = matching_capabilities[selected_index]

        # Set the selected capability ID in context
        context.set_parameter_value("selected_capability_id", selected_capability.METADATA.id)

        return {
            "cli_context": context,
        }
