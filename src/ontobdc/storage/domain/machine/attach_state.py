from ontobdc.storage.domain.port.attach_machine import (
    ContainerAttachProcessStatePort,
)


class ContainerAttachProcessState(ContainerAttachProcessStatePort):
    """States inferred from the current container attachment artefacts."""

    UNDEFINED = "__undefined__"
    CONTAINER_INSPECTED = "__container_inspected__"
    IDENTITY_RESOLVED = "__identity_resolved__"
    CONTAINER_METADATA_ATTACHED = "__container_metadata_attached__"
    DATASETS_ATTACHED = "__datasets_attached__"
    STORAGE_INDEX_ATTACHED = "__storage_index_attached__"
    CONTEXT_ATTACHED = "__context_attached__"
    CONTAINER_ATTACHED = "__container_attached__"

    INVALID_CONTAINER_PATH = "__invalid_container_path__"
    INVALID_CONTAINER_GRAPH = "__invalid_container_graph__"
    IDENTITY_CONFLICT = "__identity_conflict__"
    DATASET_ATTACH_FAILED = "__dataset_attach_failed__"
    STORAGE_INDEX_ATTACH_FAILED = "__storage_index_attach_failed__"
    ATTACH_ROLLBACK_FAILED = "__attach_rollback_failed__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.CONTAINER_INSPECTED: "Container Inspected",
                self.IDENTITY_RESOLVED: "Identity Resolved",
                self.CONTAINER_METADATA_ATTACHED: "Container Metadata Attached",
                self.DATASETS_ATTACHED: "Datasets Attached",
                self.STORAGE_INDEX_ATTACHED: "Storage Index Attached",
                self.CONTEXT_ATTACHED: "Context Attached",
                self.CONTAINER_ATTACHED: "Container Attached",
                self.INVALID_CONTAINER_PATH: "Invalid Container Path",
                self.INVALID_CONTAINER_GRAPH: "Invalid Container Graph",
                self.IDENTITY_CONFLICT: "Identity Conflict",
                self.DATASET_ATTACH_FAILED: "Dataset Attach Failed",
                self.STORAGE_INDEX_ATTACH_FAILED: "Storage Index Attach Failed",
                self.ATTACH_ROLLBACK_FAILED: "Attach Rollback Failed",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.CONTAINER_INSPECTED: "Container Inspecionado",
                self.IDENTITY_RESOLVED: "Identidade Resolvida",
                self.CONTAINER_METADATA_ATTACHED: "Metadados do Container Anexados",
                self.DATASETS_ATTACHED: "Datasets Anexados",
                self.STORAGE_INDEX_ATTACHED: "Indice de Storage Anexado",
                self.CONTEXT_ATTACHED: "Contexto Anexado",
                self.CONTAINER_ATTACHED: "Container Anexado",
                self.INVALID_CONTAINER_PATH: "Caminho do Container Invalido",
                self.INVALID_CONTAINER_GRAPH: "Grafo do Container Invalido",
                self.IDENTITY_CONFLICT: "Conflito de Identidade",
                self.DATASET_ATTACH_FAILED: "Falha ao Anexar Dataset",
                self.STORAGE_INDEX_ATTACH_FAILED: "Falha ao Anexar Indice de Storage",
                self.ATTACH_ROLLBACK_FAILED: "Falha no Rollback do Attach",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "No attachment state can be inferred yet.",
                self.CONTAINER_INSPECTED: "The imported container and its datasets were inspected without changing their metadata.",
                self.IDENTITY_RESOLVED: "The target local identities and locations were calculated and checked for conflicts.",
                self.CONTAINER_METADATA_ATTACHED: "The container metadata graph uses the target local identity and location.",
                self.DATASETS_ATTACHED: "Every dataset graph and the dataset index inside the container graph use the target identities and locations.",
                self.STORAGE_INDEX_ATTACHED: "The local storage index contains the canonical entry copied from the attached container metadata.",
                self.CONTEXT_ATTACHED: "The execution context points to the attached container and no stale update selector remains.",
                self.CONTAINER_ATTACHED: "The container, datasets, storage index, and execution context are mutually consistent.",
                self.INVALID_CONTAINER_PATH: "The requested path is not an attachable container directory inside the current project root.",
                self.INVALID_CONTAINER_GRAPH: "The imported container metadata cannot be parsed or does not identify exactly one data container.",
                self.IDENTITY_CONFLICT: "The target container or dataset identity conflicts with another local object.",
                self.DATASET_ATTACH_FAILED: "A dataset could not be migrated or validated safely.",
                self.STORAGE_INDEX_ATTACH_FAILED: "The local storage index could not be reconciled with the attached container.",
                self.ATTACH_ROLLBACK_FAILED: "The original metadata files could not be restored after a failed attachment.",
            },
            "pt-br": {
                self.UNDEFINED: "Nenhum estado do attach pode ser inferido ainda.",
                self.CONTAINER_INSPECTED: "O container importado e seus datasets foram inspecionados sem alterar os metadados.",
                self.IDENTITY_RESOLVED: "As identidades e localizacoes locais de destino foram calculadas e verificadas quanto a conflitos.",
                self.CONTAINER_METADATA_ATTACHED: "O grafo de metadados do container usa a identidade e a localizacao locais de destino.",
                self.DATASETS_ATTACHED: "Todos os grafos de dataset e o indice de datasets no container usam as identidades e localizacoes de destino.",
                self.STORAGE_INDEX_ATTACHED: "O indice de storage local contem a entrada canonica copiada dos metadados do container anexado.",
                self.CONTEXT_ATTACHED: "O contexto de execucao aponta para o container anexado e nao preserva seletores antigos de update.",
                self.CONTAINER_ATTACHED: "Container, datasets, indice de storage e contexto de execucao estao consistentes entre si.",
                self.INVALID_CONTAINER_PATH: "O caminho solicitado nao e um diretorio de container anexavel dentro do root atual.",
                self.INVALID_CONTAINER_GRAPH: "Os metadados importados nao podem ser lidos ou nao identificam exatamente um data container.",
                self.IDENTITY_CONFLICT: "A identidade de destino do container ou de um dataset conflita com outro objeto local.",
                self.DATASET_ATTACH_FAILED: "Um dataset nao pode ser migrado ou validado com seguranca.",
                self.STORAGE_INDEX_ATTACH_FAILED: "O indice de storage local nao pode ser reconciliado com o container anexado.",
                self.ATTACH_ROLLBACK_FAILED: "Os arquivos de metadados originais nao puderam ser restaurados apos uma falha no attach.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ContainerAttachProcessState":
        return getattr(ContainerAttachProcessState, state.upper())
