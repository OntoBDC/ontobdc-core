
import os
from importlib.metadata import distributions
from pathlib import Path
from typing import Any, Dict, List, Optional
from ontobdc.cli import get_config_dir, config_data
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.resource.base import BaseResource


class ConfigDataAdapter(ConfigDataPort):
    """
    Config data adapter.
    """
    def __init__(self):
        self.config_file: str = os.path.join(get_config_dir(), "config.yaml")
        self.config_data: Optional[Dict[str, Any]] = config_data()

    @property
    def path(self) -> Path:
        return Path(self.config_file)

    @property
    def data(self) -> Optional[Dict[str, Any]]:
        return self.config_data

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
        return self.config_data.get("context", {})

