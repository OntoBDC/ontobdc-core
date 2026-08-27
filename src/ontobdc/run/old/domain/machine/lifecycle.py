
from ontobdc.run.domain.port.machine import IntentStatePort


class RunIntentResolutionState(IntentStatePort):
    """
    Enum representing the possible states of the capability intent resolution process.

    Matches the states referenced in the pipeline and follows the
    localization pattern.
    """
    UNDEFINED = "__undefined__"
    EMPTY = "__empty__"
    LANGUAGE_DEFINED = "__language_defined__"
    INTENDED = "__intended__"
    PARSED = "__parsed__"
    CANONICAL = "__canonical__"
    LOW_CONFIDENCE = "__low_confidence__"
    VALIDATED = "__validated__"
    PLANNED = "__planned__"
    FILLED = "__filled__"
    UNREACHABLE = "__unreachable__"

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label for the state in the specified language.

        :param lang: Language code (default "en")
        :return: Translated label string
        """
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.EMPTY: "Empty",
                self.LANGUAGE_DEFINED: "Language Defined",
                self.INTENDED: "Intended",
                self.PARSED: "Parsed",
                self.CANONICAL: "Canonical",
                self.LOW_CONFIDENCE: "Low Confidence",
                self.VALIDATED: "Validated",
                self.PLANNED: "Planned",
                self.FILLED: "Filled",
                self.UNREACHABLE: "Unreachable",
            },
            "pt": {
                self.UNDEFINED: "Indefinido",
                self.EMPTY: "Vazio",
                self.LANGUAGE_DEFINED: "Idioma Definido",
                self.INTENDED: "Intencionado",
                self.PARSED: "Analisado",
                self.CANONICAL: "Canônico",
                self.LOW_CONFIDENCE: "Baixa Confianca",
                self.VALIDATED: "Validado",
                self.PLANNED: "Planejado",
                self.FILLED: "Preenchido",
                self.UNREACHABLE: "Inviável",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        """
        Returns the technical description for the state in the specified language.

        :param lang: Language code (default "en")
        :return: Translated description string
        """
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before intent resolution begins",
                self.EMPTY: "The handler asks the user what language they prefer",
                self.LANGUAGE_DEFINED: "The handler has the user's language preference defined",
                self.INTENDED: "The handler has the user's intended action defined",
                self.PARSED: "The handler has parsed the user's intent",
                self.CANONICAL: "The handler has the user's canonical intent defined",
                self.LOW_CONFIDENCE: "The handler parsed the user's intent, but the confidence score is insufficient",
                self.VALIDATED: "The user confirmed the resolved intent",
                self.PLANNED: "The intent resolution flow produced a support plan for the capability execution",
                self.FILLED: "The final state: capability inputs are filled and ready for execution",
                self.UNREACHABLE: "The execution plan cannot be resolved with the currently available context and inputs",
            },
            "pt": {
                self.UNDEFINED: "Estado inicial antes do inicio da resolucao de intencao",
                self.EMPTY: "O handler pergunta ao usuario qual idioma ele prefere",
                self.LANGUAGE_DEFINED: "O handler tem a preferencia de idioma do usuario definida",
                self.INTENDED: "O handler tem a intencao do usuario definida",
                self.PARSED: "O handler analisou a intencao do usuario",
                self.CANONICAL: "O handler tem a intencao canônica do usuario definida",
                self.LOW_CONFIDENCE: "O handler analisou a intencao do usuario, mas o score de confianca e insuficiente",
                self.VALIDATED: "O usuario confirmou a intencao resolvida",
                self.PLANNED: "O fluxo de resolucao de intencao produziu um plano de suporte para a execucao da capability",
                self.FILLED: "O estado final: as entradas da capability estao preenchidas e prontas para execucao",
                self.UNREACHABLE: "O plano de execucao nao pode ser resolvido com o contexto e as entradas atualmente disponiveis",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "RunIntentResolutionState":
        """
        Returns the enum value given a state name string.

        :param state: The name of the state (case-insensitive)
        :return: RunIntentResolutionState enum value
        """
        return getattr(RunIntentResolutionState, state.upper())

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.value
