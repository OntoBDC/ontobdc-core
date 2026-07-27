
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ontobdc.shared.domain.model.language import LanguageResource


class ConfigDataPort(ABC):
    """
    Port interface defining the contract for accessing project configuration data.
    """
    @property
    @abstractmethod
    def path(self) -> Path:
        """
        Gets the absolute path to the configuration file.
        """
        ...

    @property
    @abstractmethod
    def all(self) -> Optional[Dict[str, Any]]:
        """
        Gets the full configuration data as a dictionary.
        """
        ...

    @property
    @abstractmethod
    def available_languages(self) -> List[LanguageResource]:
        """
        Gets the list of available languages installed in the application.
        """
        ...

    @property
    @abstractmethod
    def root_dir(self) -> Path:
        """
        Gets the absolute path to the project's root directory.
        """
        ...

    @property
    @abstractmethod
    def script_dir(self) -> Path:
        """
        Gets the absolute path to the OntoBDC package directory.
        """
        ...

    @property
    @abstractmethod
    def config_dir(self) -> Path:
        """
        Gets the absolute path to the configuration directory (.__ontobdc__).
        """
        ...

    @property
    @abstractmethod
    def config_file(self) -> Path:
        """
        Gets the absolute path to the config.yaml file.
        """
        ...

    @property
    @abstractmethod
    def ontology_cache(self) -> Path:
        """
        Gets the absolute path to the ontology cache directory.
        """
        ...

    @property
    @abstractmethod
    def available_languages(self) -> List[LanguageResource]:
        """
        Get available languages.
        """
        ...

    @property
    @abstractmethod
    def default_language(self) -> Optional[str]:
        """
        Get default language.
        """
        ...

    @property
    @abstractmethod
    def context_data(self) -> Dict[str, Any]:
        """
        Get context data.
        """
        ...

    @abstractmethod
    def get_config_file(self, config_dir: str = None) -> str:
        """
        Get the configuration file path (config.yaml) inside the configuration directory.
        """
        ...

    @abstractmethod
    def find_project_root(self, current_dir: Path) -> Optional[Path]:
        """
        Recursively search for project root by looking for .__ontobdc__/config.yaml.
        """
        ...
