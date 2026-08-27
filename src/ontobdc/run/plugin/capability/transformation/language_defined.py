from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.a3.domain.model.language import A3SupportedLanguages
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.util import generate_hash
from ontobdc.shared.domain.model.capability import CapabilityMetadata

METADATA_DIRECTORY = ".__ontobdc__"
ETL_DIRECTORY = "etl"
RUN_ETL_DIRECTORY = "run"
STATE_EXTENSION = "txt"


class LanguageDefinedCapability(TransformationCapability):
    """Confirm the run's resolved language is one a3 recognizes.

    Raises when it is not, reporting the languages a3 does recognize --
    the same list ``ontobdc a3 --lang`` prints.

    Unlike ``PromptReceivedCapability`` (scoped by a hash of the prompt),
    this state artifact is scoped by a hash of the *language* itself: "is
    'en' a language a3 recognizes" is a fact independent of which prompt
    triggered the check, so every run sharing a language shares the same
    ETL directory and only needs to confirm it once.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "language_defined"
        ),
        version="1.0.0",
        name="Language Defined",
        description=(
            "Confirm the run's language is one a3 recognizes, or report "
            "the languages it does."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "language", "intent"],
        supported_languages=A3SupportedLanguages.list(),
    )

    def __init__(self) -> None:
        self._resolved_language: Optional[str] = None

    @property
    def metadata(self) -> CapabilityMetadata:
        # Same reasoning as PromptReceivedCapability: log_message is static
        # text, so the resolved language is interpolated here, after
        # execute() has set _resolved_language, instead of inside a
        # log_message dict.
        if self._resolved_language is None:
            return self.METADATA

        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"The run's language was set to '{self._resolved_language}'.",
                        "pt-br": f"O idioma da execucao foi definido como '{self._resolved_language}'.",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.LANGUAGE_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.LANGUAGE_DEFINED.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort, language: str) -> Path:
        return (
            Path(str(context.root_path)).expanduser().resolve()
            / METADATA_DIRECTORY
            / ETL_DIRECTORY
            / RUN_ETL_DIRECTORY
            / generate_hash({"language": language})
        )

    @classmethod
    def state_path(cls, context: CliContextPort, language: str) -> Path:
        return cls.state_directory(context, language) / (
            f"{IntentResolutionState.LANGUAGE_DEFINED.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort, language: str) -> bool:
        try:
            path = self.state_path(context, language)
            if not path.is_file():
                return False
            return path.read_text(encoding="utf-8").strip() == language
        except OSError:
            return False

    def is_satisfied(self, context: CliContextPort, language: str) -> bool:
        return self.check(context, language)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        language: str = str(context.language or "").strip().lower()
        supported_languages: List[str] = A3SupportedLanguages.list()

        if not A3SupportedLanguages.supports(language):
            raise ValueError(
                f"a3 does not recognize the language '{language}'. "
                f"Supported languages: {', '.join(supported_languages)}. "
                "Run `ontobdc a3 --lang` to see this list."
            )

        if not self.is_satisfied(context, language):
            state_path: Path = self.state_path(context, language)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(language, encoding="utf-8")

        self._resolved_language = language
        return {"language": language, "supported_languages": supported_languages}
