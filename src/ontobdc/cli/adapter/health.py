
from typing import List
from pathlib import Path
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.health import CliCommandHealthPort
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter


class NoHealthCheckAdapter(CliCommandHealthPort):
    def check(self, args: List[str], logger: LogRepositoryPort) -> bool:
        _ = args
        _ = logger

        return True


class CliBootstrapHealthAdapter(CliCommandHealthPort):
    def __init__(self) -> None:
        self._config_adapter: ConfigDataPort = self._make_config_data_adapter()

    def check(self, args: List[str], logger: LogRepositoryPort) -> bool:
        _ = args
        # raise NotImplementedError("CliBootstrapHealthAdapter.check is not implemented.")

        try:
            if not self._check_data_config(logger):
                return False
        except ProjectRootDirectoryNotSetError as e:
            logger.log_warning("Bootstrap health check skipped project-root validation because no project root is initialized yet.")
            raise e

        logger.log_info("The system is healthy for bootstrap.")
        return True

    def _check_data_config(self, logger: LogRepositoryPort) -> bool:
        if not isinstance(self._config_adapter.path, Path) or not self._config_adapter.path.exists():
            logger.log_error("ConfigDataAdapter.path is not a valid path.")
            return False

        if not isinstance(self._config_adapter.all, dict) or len(self._config_adapter.all) == 0:
            logger.log_error("ConfigDataAdapter.all is not a valid dict.")
            return False

        if not isinstance(self._config_adapter.root_dir, Path) or not self._config_adapter.root_dir.exists():
            logger.log_error("ConfigDataAdapter.root_dir is not a valid path.")
            return False

        if not isinstance(self._config_adapter.script_dir, Path) or not self._config_adapter.script_dir.exists():
            logger.log_error("ConfigDataAdapter.script_dir is not a valid path.")
            return False

        default_language = self._config_adapter.default_language
        if default_language is not None and not isinstance(default_language, str):
            logger.log_error("ConfigDataAdapter.default_language is not a valid string.")
            return False

        if not isinstance(self._config_adapter.context_data, dict):
            logger.log_error("ConfigDataAdapter.context_data is not a valid dict.")
            return False

        return True

    def _make_config_data_adapter(self) -> ConfigDataPort:
        try:
            return ConfigDataAdapter()

        except ProjectRootDirectoryNotSetError:
            pass

        return UnsetProjectRootConfigDataAdapter()
