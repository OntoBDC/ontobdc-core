from typing import Any, Optional

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.shared.domain.model.parameter import ParameterMetadata


class InstallFromGitHubStrategy(CliContextStrategyPort):
    """
    Resolve the address ``ddock --install`` is given to the zip it installs from.

    Whatever form of GitHub address the person typed, it becomes the address of
    the zip of the ``master`` branch of the repository, or of its ``main``
    branch when there is no ``master`` (GitHub is asked which exists). The
    strategy does not judge the address: one that names no GitHub repository,
    or a repository with neither branch, simply resolves to nothing, and it is
    the command's check that refuses a command with no zip.
    """

    SELECTOR_FLAG: str = "--install"
    SOURCE_KEY: str = "ddock_install_source"
    ZIP_KEY: str = "ddock_install_zip"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.ontobdc.ddock.plugin.parameter.install_from_github",
        version="1.0.0",
        name="ddock_install_source",
        description=(
            "Resolve the address given to ddock --install to the address of "
            "the zip of the master branch of its GitHub repository."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["ddock", "install", "github"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the zip the address names, or clear a stale binding.
        """
        raw_args = context.raw_args
        if self.SELECTOR_FLAG not in raw_args:
            return context

        context.delete_parameter(self.ZIP_KEY)
        address: Optional[str] = self._address(context)
        zip_address: Optional[str] = GitHubZipAddress.resolve(address) if address is not None else None
        if zip_address is not None:
            context.set_parameter_value(self.ZIP_KEY, zip_address)

        return context

    def _address(self, context: CliContextPort) -> Optional[str]:
        """
        Return the address the person typed, or None when they typed none.
        """
        value: Any = context.get_parameter_value(self.SOURCE_KEY)
        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()
