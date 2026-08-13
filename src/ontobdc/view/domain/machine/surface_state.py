from ontobdc.view.domain.port.surface_machine import SurfaceGenerationProcessStatePort


class SurfaceGenerationProcessState(SurfaceGenerationProcessStatePort):
    """Cumulative states of an offline HTML Presentation Surface artefact."""

    UNDEFINED = "__undefined__"
    CONTAINER_HEALTHY = "__container_healthy__"
    IS_PUBLISHABLE = "__is_publishable__"
    DATA_GATHERED = "__data_gathered__"
    SURFACE_INITIALIZED = "__surface_initialized__"
    SURFACE_ENRICHED = "__surface_enriched__"
    SURFACE_SET = "__surface_set__"
    SURFACE_MATCHED = "__surface_matched__"
    SURFACE_OPERATIONAL_MATCHED = "__surface_operational_matched__"
    SURFACE_ASSEMBLED = "__surface_assembled__"
    SURFACE_PACKAGED = "__surface_packaged__"
    SURFACE_VALIDATED = "__surface_validated__"
    ENTITY_VIEWS_PUBLISHED = "__entity_views_published__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.CONTAINER_HEALTHY: "Container Healthy",
                self.IS_PUBLISHABLE: "Is Publishable",
                self.DATA_GATHERED: "Data Gathered",
                self.SURFACE_INITIALIZED: "Surface Initialized",
                self.SURFACE_ENRICHED: "Surface Enriched",
                self.SURFACE_SET: "Surface Set",
                self.SURFACE_MATCHED: "Surface Matched",
                self.SURFACE_OPERATIONAL_MATCHED: "Surface Operational Matched",
                self.SURFACE_ASSEMBLED: "Surface Assembled",
                self.SURFACE_PACKAGED: "Surface Packaged",
                self.SURFACE_VALIDATED: "Surface Validated",
                self.ENTITY_VIEWS_PUBLISHED: "Entity Views Published",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinida",
                self.CONTAINER_HEALTHY: "Container Saudavel",
                self.IS_PUBLISHABLE: "Publicavel",
                self.DATA_GATHERED: "Dados Reunidos",
                self.SURFACE_INITIALIZED: "Surface Inicializada",
                self.SURFACE_ENRICHED: "Surface Enriquecida",
                self.SURFACE_SET: "Surface Configurada",
                self.SURFACE_MATCHED: "Surface Correlacionada",
                self.SURFACE_OPERATIONAL_MATCHED: "Surface Operacional Correlacionada",
                self.SURFACE_ASSEMBLED: "Surface Montada",
                self.SURFACE_PACKAGED: "Surface Empacotada",
                self.SURFACE_VALIDATED: "Surface Validada",
                self.ENTITY_VIEWS_PUBLISHED: "Views de Entidade Publicadas",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No HTML Presentation Surface artefact exists yet.",
                self.CONTAINER_HEALTHY: "The source container satisfies its structural and semantic health requirements.",
                self.IS_PUBLISHABLE: "The healthy source container has a valid publication descriptor and the resources required for presentation generation.",
                self.DATA_GATHERED: "Presentation source data has been materialized as the JSON-LD state artefact consumed by subsequent Surface transformations.",
                self.SURFACE_INITIALIZED: "The minimal offline HTML document and Presentation Surface host exist.",
                self.SURFACE_ENRICHED: "Semantic data and metadata are embedded in the HTML document as JSON-LD.",
                self.SURFACE_SET: "Surface regions and presentation rules are declared without fixing runtime viewport geometry.",
                self.SURFACE_MATCHED: "Presentation data are matched to compatible Tile definitions and their support envelopes.",
                self.SURFACE_OPERATIONAL_MATCHED: "Operational Tiles declared by any configured DefaultSurfaceLayout/PresentationSurface RDF are matched and the resolved layout candidates are embedded for client-side selection.",
                self.SURFACE_ASSEMBLED: "Operation, content and pinned regions are composed with matched Tiles and runtime layout constraints.",
                self.SURFACE_PACKAGED: "Required browser component implementations are embedded for offline execution.",
                self.SURFACE_VALIDATED: "The packaged HTML Surface satisfies the offline Surface generation checks.",
                self.ENTITY_VIEWS_PUBLISHED: "A standalone detail page was published for every entity ontobdc_view has a Page renderer for.",
            },
            "pt-br": {
                self.UNDEFINED: "Ainda nao existe artefato HTML de Presentation Surface.",
                self.CONTAINER_HEALTHY: "O container fonte atende aos requisitos de saude estrutural e semantica.",
                self.IS_PUBLISHABLE: "O container fonte saudavel possui descritor de publicacao valido e os recursos necessarios para gerar a apresentacao.",
                self.DATA_GATHERED: "Os dados fonte da apresentacao foram materializados como o artefato de estado JSON-LD consumido pelas transformacoes seguintes da Surface.",
                self.SURFACE_INITIALIZED: "O documento HTML offline minimo e o host da Presentation Surface existem.",
                self.SURFACE_ENRICHED: "Dados e metadados semanticos estao incorporados ao HTML como JSON-LD.",
                self.SURFACE_SET: "As regioes e regras da Surface estao declaradas sem fixar a geometria do viewport em runtime.",
                self.SURFACE_MATCHED: "Os dados de apresentacao estao correlacionados a Tiles compativeis e aos seus envelopes de suporte.",
                self.SURFACE_OPERATIONAL_MATCHED: "Os Tiles operacionais declarados por qualquer DefaultSurfaceLayout/PresentationSurface RDF configurado estao correlacionados e os candidatos de layout resolvidos estao incorporados para selecao no navegador.",
                self.SURFACE_ASSEMBLED: "As regioes operation, content e pinned estao compostas com Tiles e restricoes de layout de runtime.",
                self.SURFACE_PACKAGED: "As implementacoes browser necessarias estao incorporadas para execucao offline.",
                self.SURFACE_VALIDATED: "A Surface HTML empacotada atende aos checks da geracao offline.",
                self.ENTITY_VIEWS_PUBLISHED: "Foi publicada uma pagina de detalhe para cada entidade com uma Page registrada no ontobdc_view.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "SurfaceGenerationProcessState":
        return getattr(SurfaceGenerationProcessState, state.upper())
