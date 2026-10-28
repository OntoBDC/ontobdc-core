from ontobdc.ddock.plugin.machine.system_update.port import (
    SystemUpdateProcessStatePort,
)


class SystemUpdateProcessState(SystemUpdateProcessStatePort):
    """
    Enum representing the possible states of the update of a system.
    """

    UNDEFINED = "__undefined__"
    SYSTEM_DESCRIPTOR_VALID = "__system_descriptor_valid__"
    DDOCK_SOURCE_REFRESHED = "__ddock_source_refreshed__"
    PACKAGES_REFRESHED = "__packages_refreshed__"
    SYSTEM_LOCK_WRITTEN = "__system_lock_written__"
    NODE_BUILT = "__node_built__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.SYSTEM_DESCRIPTOR_VALID: "System Descriptor Valid",
                self.DDOCK_SOURCE_REFRESHED: "DDock Source Refreshed",
                self.PACKAGES_REFRESHED: "Packages Refreshed",
                self.SYSTEM_LOCK_WRITTEN: "System Lock Written",
                self.NODE_BUILT: "Node Built",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.SYSTEM_DESCRIPTOR_VALID: "Descritor do Sistema Válido",
                self.DDOCK_SOURCE_REFRESHED: "Fonte do DDock Atualizada",
                self.PACKAGES_REFRESHED: "Pacotes Atualizados",
                self.SYSTEM_LOCK_WRITTEN: "Lock do Sistema Gravado",
                self.NODE_BUILT: "Node Compilado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the update has a valid system.obdc.",
                self.SYSTEM_DESCRIPTOR_VALID: "The container has a system.obdc and it is valid.",
                self.DDOCK_SOURCE_REFRESHED: "The source folder of the container was replaced by the ddock of the repository system.obdc names.",
                self.PACKAGES_REFRESHED: "The host of each package of system.obdc was fetched again and put into the source folder of the container.",
                self.SYSTEM_LOCK_WRITTEN: "The system.obdc.lock says what was installed.",
                self.NODE_BUILT: "The node application was compiled with npm run build.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes de a atualização ter um system.obdc válido.",
                self.SYSTEM_DESCRIPTOR_VALID: "O container tem um system.obdc e ele é válido.",
                self.DDOCK_SOURCE_REFRESHED: "A pasta source do container foi substituída pelo ddock do repositório que o system.obdc nomeia.",
                self.PACKAGES_REFRESHED: "O host de cada pacote do system.obdc foi baixado de novo e posto na pasta source do container.",
                self.SYSTEM_LOCK_WRITTEN: "O system.obdc.lock diz o que foi instalado.",
                self.NODE_BUILT: "A aplicação node foi compilada com npm run build.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "SystemUpdateProcessState":
        return getattr(SystemUpdateProcessState, state.upper())
