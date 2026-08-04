from ontobdc.view.domain.port.machine import ContainerViewProcessStatePort


class ContainerViewProcessState(ContainerViewProcessStatePort):
    """States inferred from the current container view artefacts."""

    UNDEFINED = "__undefined__"
    CONTAINER_HEALTHY = "__container_healthy__"
    IS_PUBLISHABLE = "__is_publishable__"
    DATA_GATHERED = "__data_gathered__"
    GENERATED = "__generated__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.CONTAINER_HEALTHY: "Container Healthy",
                self.IS_PUBLISHABLE: "Is Publishable",
                self.DATA_GATHERED: "Data Gathered",
                self.GENERATED: "Generated",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.CONTAINER_HEALTHY: "Container Saudavel",
                self.IS_PUBLISHABLE: "Publicavel",
                self.DATA_GATHERED: "Dados Reunidos",
                self.GENERATED: "Gerado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No later container view state can be inferred from the current artefacts.",
                self.CONTAINER_HEALTHY: "The container satisfies its general structural and semantic health requirements.",
                self.IS_PUBLISHABLE: "The healthy container has a valid publishing dataset and all resources required to gather publication data.",
                self.DATA_GATHERED: "The publishing capabilities completed and the data used by the view was materialized.",
                self.GENERATED: "The requested container view representation was generated.",
            },
            "pt-br": {
                self.UNDEFINED: "Nenhum estado posterior da view do container pode ser inferido a partir dos artefatos atuais.",
                self.CONTAINER_HEALTHY: "O container atende aos requisitos gerais de saude estrutural e semantica.",
                self.IS_PUBLISHABLE: "O container saudavel possui um publishing dataset valido e todos os recursos necessarios para reunir os dados de publicacao.",
                self.DATA_GATHERED: "As capabilities de publicacao terminaram e os dados usados pela view foram materializados.",
                self.GENERATED: "A representacao de view solicitada para o container foi gerada.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ContainerViewProcessState":
        return getattr(ContainerViewProcessState, state.upper())
