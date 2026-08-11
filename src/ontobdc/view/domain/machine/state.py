from ontobdc.view.domain.port.machine import ContainerViewProcessStatePort


class ContainerViewProcessState(ContainerViewProcessStatePort):
    """States inferred from the legacy container view artefacts."""

    UNDEFINED = "__undefined__"
    DATA_GATHERED = "__data_gathered__"
    HARDCODED = "__hardcoded__"
    FACADES_SERIALIZED = "__facades_serialized__"
    DATASET_VIEWS_GENERATED = "__dataset_views_generated__"
    GENERATED = "__generated__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.DATA_GATHERED: "Data Gathered",
                self.HARDCODED: "Hardcoded",
                self.FACADES_SERIALIZED: "Facades Serialized",
                self.DATASET_VIEWS_GENERATED: "Dataset Views Generated",
                self.GENERATED: "Generated",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.DATA_GATHERED: "Dados Reunidos",
                self.HARDCODED: "Hardcoded",
                self.FACADES_SERIALIZED: "Facades Serializadas",
                self.DATASET_VIEWS_GENERATED: "Views dos Datasets Geradas",
                self.GENERATED: "Gerado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No later legacy container view state can be inferred from the current artefacts.",
                self.DATA_GATHERED: "The publishing capabilities completed and the data used by the legacy view was materialized.",
                self.HARDCODED: "View-generation operations that have not yet been formalized were executed.",
                self.FACADES_SERIALIZED: "Every dataset was materialized through its facade; the contracts and resulting instances were serialized as JSON-LD and embedded in the container view.",
                self.DATASET_VIEWS_GENERATED: "The WorkStream and IfcWorkSchedule pages declared by datasets were rendered from Jinja templates.",
                self.GENERATED: "The requested legacy container view representation was generated.",
            },
            "pt-br": {
                self.UNDEFINED: "Nenhum estado posterior da view legada do container pode ser inferido a partir dos artefatos atuais.",
                self.DATA_GATHERED: "As capabilities de publicacao terminaram e os dados usados pela view legada foram materializados.",
                self.HARDCODED: "As operacoes de geracao de views ainda nao oficializadas foram executadas.",
                self.FACADES_SERIALIZED: "Cada dataset foi materializado por sua facade; os contratos e as instancias resultantes foram serializados como JSON-LD e incorporados a view do container.",
                self.DATASET_VIEWS_GENERATED: "As paginas de WorkStream e IfcWorkSchedule declaradas pelos datasets foram renderizadas a partir de templates Jinja.",
                self.GENERATED: "A representacao de view legada solicitada para o container foi gerada.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ContainerViewProcessState":
        return getattr(ContainerViewProcessState, state.upper())
