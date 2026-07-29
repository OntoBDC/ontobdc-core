from enum import Enum


class EntityLearningProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    IDENTIFIED = "__identified__"
    EXTRACTED = "__extracted__"
    SPATIALIZED = "__spatialized__"
    ALIGNED = "__aligned__"
    PUBLISHED = "__published__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.IDENTIFIED: "Identified",
                self.EXTRACTED: "Extracted",
                self.SPATIALIZED: "Spatialized",
                self.ALIGNED: "Aligned",
                self.PUBLISHED: "Published",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.IDENTIFIED: "Identificado",
                self.EXTRACTED: "Extraido",
                self.SPATIALIZED: "Espacializado",
                self.ALIGNED: "Alinhado",
                self.PUBLISHED: "Publicado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the learning source is identified.",
                self.IDENTIFIED: "The source file was identified and stored in the learning pipeline.",
                self.EXTRACTED: "The source file produced extractable text content.",
                self.SPATIALIZED: "The extracted content was enriched with bounding boxes.",
                self.ALIGNED: "The spatialized content produced a deterministic aligned vector.",
                self.PUBLISHED: "The learning result was published into context.ttl.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da identificacao da fonte de aprendizado.",
                self.IDENTIFIED: "O arquivo fonte foi identificado e armazenado no pipeline de aprendizado.",
                self.EXTRACTED: "O arquivo fonte produziu conteudo textual extraivel.",
                self.SPATIALIZED: "O conteudo extraido foi enriquecido com bounding boxes.",
                self.ALIGNED: "O conteudo espacializado produziu um vetor alinhado deterministico.",
                self.PUBLISHED: "O resultado do aprendizado foi publicado no context.ttl.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "EntityLearningProcessState":
        return getattr(EntityLearningProcessState, state.upper())


class EntityAnalysisProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    IDENTIFIED = "__identified__"
    EXTRACTED = "__extracted__"
    SPATIALIZED = "__spatialized__"
    ALIGNED = "__aligned__"
    ORIGIN_RESOLVED = "__origin_resolved__"
    VECTORS_LOADED = "__vectors_loaded__"
    SCORED = "__scored__"
    ANALYSED = "__analysed__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.IDENTIFIED: "Identified",
                self.EXTRACTED: "Extracted",
                self.SPATIALIZED: "Spatialized",
                self.ALIGNED: "Aligned",
                self.ORIGIN_RESOLVED: "Origin Resolved",
                self.VECTORS_LOADED: "Vectors Loaded",
                self.SCORED: "Scored",
                self.ANALYSED: "Analysed",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.IDENTIFIED: "Identificado",
                self.EXTRACTED: "Extraido",
                self.SPATIALIZED: "Espacializado",
                self.ALIGNED: "Alinhado",
                self.ORIGIN_RESOLVED: "Origem Resolvida",
                self.VECTORS_LOADED: "Vetores Carregados",
                self.SCORED: "Pontuado",
                self.ANALYSED: "Analisado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the analysis source is identified.",
                self.IDENTIFIED: "The source file was identified and stored in the analysis pipeline.",
                self.EXTRACTED: "The source file produced extractable text content.",
                self.SPATIALIZED: "The extracted content was enriched with bounding boxes.",
                self.ALIGNED: "The spatialized content produced a deterministic aligned vector.",
                self.ORIGIN_RESOLVED: "The registered vector sources were resolved.",
                self.VECTORS_LOADED: "The registered vector candidates were loaded.",
                self.SCORED: "The loaded vector candidates were scored against the aligned file vector.",
                self.ANALYSED: "The aligned content was analysed against available vector candidates.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da identificacao da fonte de analise.",
                self.IDENTIFIED: "O arquivo fonte foi identificado e armazenado no pipeline de analise.",
                self.EXTRACTED: "O arquivo fonte produziu conteudo textual extraivel.",
                self.SPATIALIZED: "O conteudo extraido foi enriquecido com bounding boxes.",
                self.ALIGNED: "O conteudo espacializado produziu um vetor alinhado deterministico.",
                self.ORIGIN_RESOLVED: "As origens registradas de vetores foram resolvidas.",
                self.VECTORS_LOADED: "Os candidatos vetoriais registrados foram carregados.",
                self.SCORED: "Os candidatos vetoriais carregados foram pontuados contra o vetor do arquivo.",
                self.ANALYSED: "O conteudo alinhado foi analisado contra os vetores disponiveis.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "EntityAnalysisProcessState":
        return getattr(EntityAnalysisProcessState, state.upper())
