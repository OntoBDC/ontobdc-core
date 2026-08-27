from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.has_english_nlp_model.check import (
    ENGLISH_NLP_MODEL_NAME,
    main as check_english_nlp_model,
)
from ontobdc.cli.plugin.check.has_english_nlp_model.hotfix import (
    main as hotfix_english_nlp_model,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class EnglishNlpModelReadyCapability(TransactionCapability):
    """Ensure the small English spaCy model (``en_core_web_sm``) is
    installed, downloading it if it is missing.

    English only, on purpose: it's the language every ``run`` intent-
    resolution pipeline can rely on regardless of the project's own
    ``--language``. Other languages' models (e.g. ``pt_core_news_sm``) are
    not installed here; they are the responsibility of whatever sets that
    language for a run (see ``ViewLanguageStrategy``).
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.cli.plugin.capability.transformation.target."
            "english_nlp_model_ready"
        ),
        version="1.0.0",
        name="English NLP Model Ready",
        description=(
            "Ensure the small English spaCy model is installed for the "
            "CLI init flow."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "init", "nlp", "spacy"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    f"The small English spaCy model ({ENGLISH_NLP_MODEL_NAME}) "
                    "is installed."
                ),
            },
            "debug_entry": {
                "en": (
                    f"Ensuring the small English spaCy model "
                    f"({ENGLISH_NLP_MODEL_NAME}) is installed."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.ENGLISH_NLP_MODEL_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.ENGLISH_NLP_MODEL_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if check_english_nlp_model() != 0:
            if hotfix_english_nlp_model() != 0:
                raise ValueError(
                    f"Failed to install the spaCy model "
                    f"'{ENGLISH_NLP_MODEL_NAME}' during CLI init."
                )

        if check_english_nlp_model() != 0:
            raise ValueError(
                f"spaCy model '{ENGLISH_NLP_MODEL_NAME}' is still missing "
                "after the CLI init hotfix."
            )

        return {
            "resulting_state": CliInitProcessState.ENGLISH_NLP_MODEL_READY,
            "model_name": ENGLISH_NLP_MODEL_NAME,
        }
