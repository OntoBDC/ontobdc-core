
import os
import yaml
import subprocess
from pathlib import Path
from importlib.metadata import distributions
from typing import Any, Dict, List, Optional
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.resource.base import BaseResource


class ConfigDataAdapter(ConfigDataPort):
    """
    Config data adapter.
    """
    def __init__(self):
        self._root_dir: str = self._get_root_dir()
        self._config_dir: str = os.path.join(self._root_dir, ".__ontobdc__")
        self._config_file: str = os.path.join(self._config_dir, "config.yaml")

        self._script_dir: str = self._get_script_dir()
        self._config_data: Dict[str, Any] = self._get_config_data()
        self._context_data: Dict[str, Any] = self._config_data.get("context", {})

    @property
    def path(self) -> Path:
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
        return Path(self._root_dir)

    @property
    def script_dir(self) -> Path:
        return Path(self._script_dir)

    @property
    def config_dir(self) -> Path:
        return Path(self._config_dir)

    @property
    def config_file(self) -> Path:
        return Path(self._config_file)

    @property
    def available_languages(self) -> List[BaseResource]:
        """
        Get available languages.
        """
        languages: List[BaseResource] = []

        for distribution in distributions():
            package_name = distribution.metadata.get("Name", "").strip()
            if not package_name or "_core_" not in package_name:
                continue

            language_id = package_name.split("_core_", 1)[0]
            description = None

            languages.append(
                BaseResource(
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

    def _find_root_dir(self, path: str = os.getcwd()) -> Optional[str]:
        """
        Find the root directory of the project.
        
        The complex resolution and recursive search has been moved to the
        'is_root_dir_set' check and hotfix to prevent fatal exceptions during
        CLI initialization when the config file is missing.
        """
        if path.strip() == "/":
            return None

        if not os.path.isdir(path):
            return self._find_root_dir(str(Path(path).parent))

        config_dir: Path = Path(path) / ".__ontobdc__"
        if not config_dir.exists():
            return self._find_root_dir(str(Path(path).parent))

        config_file: Optional[str] = self.get_config_file(str(config_dir))

        if not os.path.exists(config_file):
            return self._find_root_dir(str(Path(path).parent))

        return path

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

        raise FileNotFoundError("Project root directory not set.")

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
                package_path = ontobdc.__path__[0]
                return package_path
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

                # engine = cfg.get("engine")
                # if not engine or engine not in VALID_ENGINES:
                #     return None

                return cfg
        except Exception:
            return None