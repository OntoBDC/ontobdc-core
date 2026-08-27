from ontobdc.run.domain.port.machine import IntentResolutionStatePort


class IntentResolutionState(IntentResolutionStatePort):
    """
    Enum representing the possible states of the run intent-resolution
    process.

    Wired so far: undefined -> received -> language_defined -> canonical
    -> parsed -> (matched | low_confidence ->) validated. ``parsed``
    branches on the parsed score: sufficient goes to ``matched`` (which
    resolves candidate capabilities directly from the parsed intent's noun
    root), insufficient goes through ``low_confidence`` first (which must
    itself resolve successfully -- matching at least one capability by tag
    -- before it can reach ``validated``). Either way, ``validated`` is
    only ever reached once some state upstream has already found candidate
    capabilities to choose among. ``intended`` (between language_defined
    and canonical in the original design) is deliberately skipped for now.
    The remaining states (planned, filled, unreachable) are not
    implemented yet.
    """

    UNDEFINED = "__undefined__"
    RECEIVED = "__received__"
    LANGUAGE_DEFINED = "__language_defined__"
    CANONICAL = "__canonical__"
    PARSED = "__parsed__"
    LOW_CONFIDENCE = "__low_confidence__"
    MATCHED = "__matched__"
    VALIDATED = "__validated__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.RECEIVED: "Received",
                self.LANGUAGE_DEFINED: "Language Defined",
                self.CANONICAL: "Canonical",
                self.PARSED: "Parsed",
                self.LOW_CONFIDENCE: "Low Confidence",
                self.MATCHED: "Matched",
                self.VALIDATED: "Validated",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.RECEIVED: "Recebido",
                self.LANGUAGE_DEFINED: "Idioma Definido",
                self.CANONICAL: "Canonico",
                self.PARSED: "Analisado",
                self.LOW_CONFIDENCE: "Baixa Confianca",
                self.MATCHED: "Correspondido",
                self.VALIDATED: "Validado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before intent resolution begins.",
                self.RECEIVED: "The prompt has been received.",
                self.LANGUAGE_DEFINED: "The run's language is confirmed to be one a3 recognizes.",
                self.CANONICAL: "The prompt has been normalized to a stable canonical form.",
                self.PARSED: "The canonical intent has been parsed (POS tags, entities, dependencies, root) and scored.",
                self.LOW_CONFIDENCE: "The parsed score was insufficient; capability tag matching was attempted from the parsed intent's noun root.",
                self.MATCHED: "The parsed score was sufficient; candidate capabilities were matched by tag directly from the parsed intent's noun root.",
                self.VALIDATED: "The user confirmed which matched capability they meant; intent resolution stops here for now.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes do inicio da resolucao de intencao.",
                self.RECEIVED: "O prompt foi recebido.",
                self.LANGUAGE_DEFINED: "O idioma da execucao foi confirmado como reconhecido pelo a3.",
                self.CANONICAL: "O prompt foi normalizado para uma forma canonica estavel.",
                self.PARSED: "A intencao canonica foi analisada (classes gramaticais, entidades, dependencias, raiz) e pontuada.",
                self.LOW_CONFIDENCE: "O score da analise foi insuficiente; foi tentada uma correspondencia por tag de capability a partir da raiz substantiva da intencao analisada.",
                self.MATCHED: "O score da analise foi suficiente; capabilities candidatas foram correspondidas por tag diretamente a partir da raiz substantiva da intencao analisada.",
                self.VALIDATED: "O usuario confirmou qual capability correspondente ele quis dizer; a resolucao de intencao para por aqui por enquanto.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "IntentResolutionState":
        return getattr(IntentResolutionState, state.upper())
