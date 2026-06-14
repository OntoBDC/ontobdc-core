
from typing import Any, Dict, List, Optional
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.resource.base import BaseResource
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.context import PromptChoiceAwarePort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from ontobdc.run.domain.exception.intent import UserCanceledCapabilitySelectionException
from ontobdc.shared.domain.resource.capability import CapabilityMetadata, TransformationCapability


class ResolutionToLanguageDefinedCapability(TransformationCapability, LoggerAwarePort, PromptChoiceAwarePort):
    """
    Capability for resolving user language preference via prompt.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.language_defined",
        version="0.1.0",
        name="Language Preference Resolution",
        description="Ask user which language they prefer.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "language", "resolution"],
            "pt": ["dados", "idioma", "resolução"],
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
                    "description": "The updated context port with the user's language preference.",
                },
            },
        },
    )

    @property
    def exit_from_language(self) -> str:
        """
        Returns the exit language function.
        """
        return "Exit"

    def __init__(self):
        self._log_strategy : Optional[LogStrategyContainerPort] = None
        self._prompt_choice : Optional[callable] = None


    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Language Preference Resolution",
            "pt": "Resolução de Preferência de Idioma",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Ask user which language they prefer.",
            "pt": "Pergunta ao usuário qual idioma ele prefere.",
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

    def _get_language(self, context: CliContextPort) -> str:
        """
        Get the language from the config file.
        Returns:
            The language from the config file.
        """
        language: Optional[str] = context.language

        language: Optional[str] = context.language
        if language:
            return language

        config_adapter: ConfigDataPort = ConfigDataAdapter()
        languages: List[BaseResource] = config_adapter.available_languages

        if languages and len(languages) == 1:
            return languages[0].id

        if language in [lang.id for lang in languages]:
            return language

        return self._prompt_choice(
            "Context",
            "Please select your preferred language",
            [f"{'English' if lang.id == 'en' else ('Português' if lang.id == 'pt' else lang.name)} ({lang.id})" for lang in languages],
            default=language,
            language="en",
            none=self.exit_from_language,
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to resolve user language preference.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the user's language preference.
        """
        language: str = self._get_language(context)
        if language == self.exit_from_language:
            raise UserCanceledCapabilitySelectionException("User exited the language resolution process.")

        context.set_parameter_value('context_language', language)

        return {
            "cli_context": context,
        }

