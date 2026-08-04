from pathlib import Path
from typing import List, Optional

from ontobdc.cli.domain.port.health import CliCommandHealthPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.config import (
    ConfigDataAdapter,
    UnsetProjectRootConfigDataAdapter,
)
from ontobdc.shared.domain.exception.config import (
    ProjectRootDirectoryNotSetError,
)
from ontobdc.shared.domain.port.config import ConfigDataPort


class NoHealthCheckAdapter(CliCommandHealthPort):
    def check(self, args: List[str], logger: LogRepositoryPort) -> bool:
        _ = args
        _ = logger

        return True


class CliBootstrapHealthAdapter(CliCommandHealthPort):
    _PROJECT_ROOT_OPTIONAL_COMMANDS = frozenset({"dev"})

    def __init__(self) -> None:
        self._config_adapter: Optional[ConfigDataPort] = None

    def check(self, args: List[str], logger: LogRepositoryPort) -> bool:
        if self._is_project_root_optional(args):
            return True

        self._config_adapter = self._make_config_data_adapter()
        try:
            if not self._check_data_config(logger):
                return False
        except ProjectRootDirectoryNotSetError as exception:
            logger.log_warning(
                "Bootstrap health check skipped project-root validation "
                "because no project root is initialized yet."
            )
            raise exception

        logger.log_info("The system is healthy for bootstrap.")
        return True

    def _is_project_root_optional(self, args: List[str]) -> bool:
        return (
            len(args) > 0
            and args[0] in self._PROJECT_ROOT_OPTIONAL_COMMANDS
        )

    def _check_data_config(self, logger: LogRepositoryPort) -> bool:
        config_adapter: ConfigDataPort = self._resolved_config_adapter()
        if (
            not isinstance(config_adapter.path, Path)
            or not config_adapter.path.exists()
        ):
            logger.log_error("ConfigDataAdapter.path is not a valid path.")
            return False

        if (
            not isinstance(config_adapter.all, dict)
            or len(config_adapter.all) == 0
        ):
            logger.log_error("ConfigDataAdapter.all is not a valid dict.")
            return False

        if (
            not isinstance(config_adapter.root_dir, Path)
            or not config_adapter.root_dir.exists()
        ):
            logger.log_error(
                "ConfigDataAdapter.root_dir is not a valid path."
            )
            return False

        if (
            not isinstance(config_adapter.script_dir, Path)
            or not config_adapter.script_dir.exists()
        ):
            logger.log_error(
                "ConfigDataAdapter.script_dir is not a valid path."
            )
            return False

        default_language = config_adapter.default_language
        if (
            default_language is not None
            and not isinstance(default_language, str)
        ):
            logger.log_error(
                "ConfigDataAdapter.default_language is not a valid string."
            )
            return False

        if not isinstance(config_adapter.context_data, dict):
            logger.log_error(
                "ConfigDataAdapter.context_data is not a valid dict."
            )
            return False

        return True

    def _resolved_config_adapter(self) -> ConfigDataPort:
        if self._config_adapter is None:
            raise RuntimeError(
                "Bootstrap config adapter was not initialized."
            )

        return self._config_adapter

    def _make_config_data_adapter(self) -> ConfigDataPort:
        try:
            return ConfigDataAdapter()
        except ProjectRootDirectoryNotSetError:
            return UnsetProjectRootConfigDataAdapter()
