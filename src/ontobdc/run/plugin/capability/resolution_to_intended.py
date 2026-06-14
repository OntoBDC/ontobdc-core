
from typing import Any, Dict, Optional
from ontobdc.shared.domain.port.context import CliContextPort, PromptRawTextAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class ResolutionToIntendedCapability(TransformationCapability, LoggerAwarePort, PromptRawTextAwarePort):
    """
    Capability for resolving user intent via prompt.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.intended",
        version="0.1.0",
        name="User Intent Resolution",
        description="Ask user what they need and capture the response.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "intent", "resolution"],
            "pt": ["dados", "intenção", "resolução"],
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
                    "description": "The updated context port with the user's intent parameter.",
                },
            },
        },
    )

    def __init__(self):
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_raw_text: Optional[callable] = None

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "User Intent Resolution",
            "pt": "Resolução de Intenção do Usuário",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Ask user what they need and capture the response.",
            "pt": "Pergunta ao usuário do que ele precisa e captura a resposta.",
        }
        return descriptions.get(lang, descriptions["en"])

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_raw_text(self, prompt_raw_text: callable):
        self._prompt_raw_text = prompt_raw_text

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        """
        Returns the log strategy container.
        """
        return self._log_strategy

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to resolve user intent.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the user's intent.
        """
        if self._prompt_raw_text is None:
            raise RuntimeError("Prompt raw text function is not configured.")

        prompts = {
            "en": "What do you need?",
            "pt": "Em que posso ajudar?",
        }
        prompt_text = prompts.get(context.language)
        user_intent = self._prompt_raw_text(prompt_text, language=context.language)

        if not user_intent:
            raise ValueError("User intent cannot be empty.")

        context.set_parameter_value("user_intent", user_intent)

        return {
            "cli_context": context,
        }
