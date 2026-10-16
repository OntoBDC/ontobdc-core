from ontobdc.ddock.plugin.machine.system_install.port import (
    SystemInstallProcessStatePort,
)


class SystemInstallProcessState(SystemInstallProcessStatePort):
    """
    Enum representing the possible states of the installation of a system.
    """

    UNDEFINED = "__undefined__"
    SYSTEM_DESCRIPTOR_VALID = "__system_descriptor_valid__"
    PYTHON_DEPENDENCIES_INSTALLED = "__python_dependencies_installed__"
    DDOCK_ZIP_EXTRACTED = "__ddock_zip_extracted__"
    DDOCK_SOURCE_MOVED = "__ddock_source_moved__"
    PACKAGES_EXTRACTED = "__packages_extracted__"
    PACKAGES_HOST_MOVED = "__packages_host_moved__"
    SYSTEM_LOCK_WRITTEN = "__system_lock_written__"
    NODE_BUILT = "__node_built__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.SYSTEM_DESCRIPTOR_VALID: "System Descriptor Valid",
                self.PYTHON_DEPENDENCIES_INSTALLED: "Python Dependencies Installed",
                self.DDOCK_ZIP_EXTRACTED: "DDock Zip Extracted",
                self.DDOCK_SOURCE_MOVED: "DDock Source Moved",
                self.PACKAGES_EXTRACTED: "Packages Extracted",
                self.PACKAGES_HOST_MOVED: "Packages Host Moved",
                self.SYSTEM_LOCK_WRITTEN: "System Lock Written",
                self.NODE_BUILT: "Node Built",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.SYSTEM_DESCRIPTOR_VALID: "Descritor do Sistema Válido",
                self.PYTHON_DEPENDENCIES_INSTALLED: "Dependências Python Instaladas",
                self.DDOCK_ZIP_EXTRACTED: "Zip do DDock Descompactado",
                self.DDOCK_SOURCE_MOVED: "Fonte do DDock Movida",
                self.PACKAGES_EXTRACTED: "Pacotes Descompactados",
                self.PACKAGES_HOST_MOVED: "Host dos Pacotes Movido",
                self.SYSTEM_LOCK_WRITTEN: "Lock do Sistema Gravado",
                self.NODE_BUILT: "Node Compilado",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: "Initial state before the installation has a valid system.obdc.",
                self.SYSTEM_DESCRIPTOR_VALID: "The project has a system.obdc and it is valid.",
                self.PYTHON_DEPENDENCIES_INSTALLED: "The Python dependencies of system.obdc are installed, at the versions it asks for.",
                self.DDOCK_ZIP_EXTRACTED: "The zip of ddock was downloaded and unpacked.",
                self.DDOCK_SOURCE_MOVED: "The folder of ddock that system.obdc names as source is in the project.",
                self.PACKAGES_EXTRACTED: "The zip of each package of system.obdc was downloaded and unpacked.",
                self.PACKAGES_HOST_MOVED: "The contents of src/host of each package are in the source folder of the project.",
                self.SYSTEM_LOCK_WRITTEN: "The system.obdc.lock says what was installed.",
                self.NODE_BUILT: "The node application was compiled with npm run build.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes de a instalação ter um system.obdc válido.",
                self.SYSTEM_DESCRIPTOR_VALID: "O projeto tem um system.obdc e ele é válido.",
                self.PYTHON_DEPENDENCIES_INSTALLED: "As dependências Python do system.obdc estão instaladas, nas versões que ele pede.",
                self.DDOCK_ZIP_EXTRACTED: "O zip do ddock foi baixado e descompactado.",
                self.DDOCK_SOURCE_MOVED: "A pasta do ddock que o system.obdc nomeia como source está no projeto.",
                self.PACKAGES_EXTRACTED: "O zip de cada pacote do system.obdc foi baixado e descompactado.",
                self.PACKAGES_HOST_MOVED: "O conteúdo de src/host de cada pacote está na pasta source do projeto.",
                self.SYSTEM_LOCK_WRITTEN: "O system.obdc.lock diz o que foi instalado.",
                self.NODE_BUILT: "A aplicação node foi compilada com npm run build.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "SystemInstallProcessState":
        return getattr(SystemInstallProcessState, state.upper())
