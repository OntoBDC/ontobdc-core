
import os
import yaml
import subprocess
from pathlib import Path
from importlib.metadata import distributions
from typing import Any, Dict, List, Optional

from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.model.language import LanguageResource
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError


class ConfigDataAdapter(ConfigDataPort):
    """
    Adapter for retrieving and managing configuration data for the OntoBDC application.
    It reads settings from the `.__ontobdc__/config.yaml` file located in the project root.
    """
    def __init__(self, root_dir: str = None):
        self._root_dir: str = root_dir
        if not isinstance(self._root_dir, str):
            try:
                self._root_dir = self._get_root_dir()
            except ProjectRootDirectoryNotSetError as e:
                raise e

        self._config_dir: str = os.path.join(self._root_dir, ".__ontobdc__")
        self._config_file: str = os.path.join(self._config_dir, "config.yaml")

        self._script_dir: str = self._get_script_dir()
        self._config_data: Dict[str, Any] = self._get_config_data()
        self._context_data: Dict[str, Any] = self._config_data.get("context", {})

    @property
    def path(self) -> Path:
        """
        Gets the absolute path to the project's config.yaml file.
        """
        return Path(self._config_file)

    @property
    def all(self) -> Optional[Dict[str, Any]]:
        """
        Get all config data.
        """
        if not self._config_data:
            self._config_data = self._get_config_data()

        return self._config_data

    @property
    def root_dir(self) -> Path:
        """
        Gets the absolute path to the project's root directory.
        """
        return Path(self._root_dir)

    @property
    def script_dir(self) -> Path:
        """
        Gets the absolute path to the OntoBDC package directory.
        """
        return Path(self._script_dir)

    @property
    def config_dir(self) -> Path:
        """
        Gets the absolute path to the configuration directory (.__ontobdc__).
        """
        return Path(self._config_dir)

    @property
    def config_file(self) -> Path:
        """
        Gets the absolute path to the config.yaml file.
        """
        return Path(self._config_file)

    @property
    def ontology_cache(self) -> Path:
        """
        Gets the absolute path to the ontology cache directory.
        """
        return Path(self._config_dir) / "ontology"

    @property
    def available_languages(self) -> List[LanguageResource]:
        """
        Get available languages.
        """
        languages: List[LanguageResource] = []

        for distribution in distributions():
            package_name = distribution.metadata.get("Name", "").strip()
            if not package_name or "_core_" not in package_name:
                continue

            language_id = package_name.split("_core_", 1)[0]
            description = None

            languages.append(
                LanguageResource(
                    id=language_id,
                    name=package_name,
                    description=description,
                )
            )

        languages.sort(key=lambda resource: resource.name)
        return languages

    @property
    def default_language(self) -> Optional[str]:
        """
        Get default language.
        """
        lang: str = self.context_data.get("obdc", {}).get("contextLanguage", None)

        if lang in [lang.id for lang in self.available_languages]:
            return lang

        return None

    @property
    def context_data(self) -> Dict[str, Any]:
        """
        Get context data.
        """
        return self._context_data

    def get_config_file(self, config_dir: str = None) -> str:
        """
        Get the configuration file path (config.yaml) inside the configuration directory.
        """
        if not config_dir or not os.path.exists(config_dir):
            config_dir = self._config_dir

        return os.path.join(config_dir, "config.yaml")

    def find_project_root(self, current_dir: Path) -> Optional[Path]:
        """Recursively search for project root by looking for .__ontobdc__/config.yaml."""
        config_file: Path = Path(self.get_config_file(current_dir))
        if config_file.is_file():
            return current_dir

        parent_dir = current_dir.parent
        if parent_dir == current_dir:
            return None

        return self.find_project_root(parent_dir)

    def _find_root_dir(self, path: Optional[str] = None) -> Optional[str]:
        """Find the nearest project root and stop safely at any filesystem root."""
        current_path: Path = Path(path or os.getcwd()).expanduser().resolve()

        while True:
            config_file: Path = current_path / ".__ontobdc__" / "config.yaml"
            if config_file.is_file():
                return str(current_path)

            parent_path: Path = current_path.parent
            if parent_path == current_path:
                return None

            current_path = parent_path

    def _get_root_dir(self) -> str:
        """
        Get the directory where the project root is stored.
        
        Returns:
            The path to the project root directory
        """
        project_root: Optional[str] = os.environ.get("ONTOBDC_PROJECT_ROOT")
        if project_root and os.path.exists(project_root):
            return project_root

        try:
            project_root = self._find_root_dir()
            if project_root and os.path.exists(project_root):
                return project_root

        except FileNotFoundError:
            pass
        
        discovered_root: Path = self.find_project_root(Path.cwd().resolve())
        if discovered_root and discovered_root.exists():
                return str(discovered_root.resolve())

        raise ProjectRootDirectoryNotSetError("Project root directory not set.")

    def _get_script_dir(self) -> str:
        """
        Get the module root directory (ontobdc/).
        
        Tries multiple strategies:
        1. Uses the installed package path
        2. Uses pip show to find the location
        3. Falls back to the current file's directory
        """
        try:
            import ontobdc
            if hasattr(ontobdc, '__path__'):
                package_path: str
                for package_path in list(ontobdc.__path__):
                    candidate_path: Path = Path(package_path).expanduser().resolve()
                    if all((candidate_path / directory_name).is_dir() for directory_name in ["cli", "shared"]):
                        return str(candidate_path)

                package_path = list(ontobdc.__path__)[0]
                return str(Path(package_path).expanduser().resolve())
        except Exception:
            pass

        try:
            # pip show ontobdc | grep Location
            location = subprocess.check_output(["pip", "show", "ontobdc", "|", "grep", "Location"]).decode("utf-8").split(":")[1].strip()
            if location:
                return os.path.join(location, "ontobdc")
        except Exception:
            pass

        script_dir = os.path.dirname(os.path.abspath(__file__))
        module_root = os.path.abspath(os.path.join(script_dir, ".."))

        return module_root

    def _get_config_data(self) -> Optional[Dict[str, Any]]:
        """
        Load and validate the project configuration from .__ontobdc__/config.yaml.
        
        Returns:
            The validated configuration dictionary, or None if invalid or missing.
        """
        config_file: str = self.get_config_file()

        if not os.path.isfile(config_file):
            return None

        try:
            with open(config_file, "r") as f:
                cfg = yaml.safe_load(f) or {}
                directory = cfg.get("directory")
                if not isinstance(directory, dict):
                    directory = {}
                    cfg["directory"] = directory

                root = directory.get("root")
                if not isinstance(root, dict):
                    root = {}
                    directory["root"] = root

                if not root.get("absolute_path"):
                    root["absolute_path"] = self._root_dir

                return cfg
        except Exception:
            return None


class UnsetProjectRootConfigDataAdapter(ConfigDataAdapter):
    """
    Adapter for contexts where the project root directory
    is intentionally unavailable.
    """
    def __init__(self):
        self._root_dir: Optional[str] = None
        self._config_dir: Optional[str] = None
        self._config_file: Optional[str] = None
        self._config_data: Optional[Dict[str, Any]] = None
        self._context_data: Dict[str, Any] = {}
        self._script_dir: str = self._get_script_dir()

    @property
    def path(self) -> Path:
        """
        Gets the absolute path to the config.yaml file.
        """
        self._raise_project_root_not_set()

    @property
    def all(self) -> Optional[Dict[str, Any]]:
        """
        Get all config data.
        """
        self._raise_project_root_not_set()

    @property
    def root_dir(self) -> Path:
        """
        Gets the absolute path to the project's root directory.
        """
        self._raise_project_root_not_set()

    @property
    def config_dir(self) -> Path:
        """
        Gets the absolute path to the configuration directory (.__ontobdc__).
        """
        self._raise_project_root_not_set()

    @property
    def config_file(self) -> Path:
        """
        Gets the absolute path to the config.yaml file.
        """
        self._raise_project_root_not_set()

    @property
    def ontology_cache(self) -> Path:
        """
        Gets the absolute path to the ontology cache directory.
        """
        self._raise_project_root_not_set()

    def get_config_file(self, config_dir: str = None) -> str:
        """
        Get the configuration file path (config.yaml) inside the configuration directory.
        """
        self._raise_project_root_not_set()

    def find_project_root(self, current_dir: Path) -> Optional[Path]:
        """
        Recursively search for project root by looking for .__ontobdc__/config.yaml.
        """
        self._raise_project_root_not_set()

    def _raise_project_root_not_set(self) -> None:
        raise ProjectRootDirectoryNotSetError()
