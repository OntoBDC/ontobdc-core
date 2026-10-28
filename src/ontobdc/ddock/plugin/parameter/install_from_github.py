from typing import ClassVar, Optional

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.shared.domain.model.parameter import ParameterMetadata


class InstallFromGitHubStrategy(CliContextStrategyPort):
    """
    Resolve the GitHub repository selected by ``ddock --install`` to its zip.

    An omitted repository selects the official OntoBDC dDock. An explicit
    repository takes precedence; in either case the first available branch
    among master and main supplies the zip, and the address of the repository
    the install comes from is bound so that system.obdc can record it. An
    invalid or unreachable repository is left unresolved for the command's
    check to reject.
    """

    SELECTOR_FLAG: ClassVar[str] = "--install"
    SOURCE_KEY: ClassVar[str] = "ddock_install_source"
    ZIP_KEY: ClassVar[str] = "ddock_install_zip"
    DEFAULT_REPOSITORY: ClassVar[str] = GitHubZipAddress.DEFAULT_REPOSITORY

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.ontobdc.ddock.plugin.parameter.install_from_github",
        version="1.0.0",
        name="ddock_install_source",
        description=(
            "Resolve ddock --install to the GitHub zip of the selected "
            "repository, defaulting to the official OntoBDC dDock."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["ddock", "install", "github"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the repository the install comes from and its resolved zip. An
        omitted argument never reuses a repository left in the context by an
        earlier command.
        """
        raw_args = context.raw_args
        if self.SELECTOR_FLAG not in raw_args:
            return context

        context.delete_parameter(self.ZIP_KEY)
        address: Optional[str] = self._address(raw_args)
        if address is None:
            return context

        repository: Optional[str] = GitHubZipAddress.repository_address(address)
        if repository is None:
            return context

        context.set_parameter_value(self.SOURCE_KEY, repository)
        zip_address: Optional[str] = GitHubZipAddress.resolve(address)
        if zip_address is not None:
            context.set_parameter_value(self.ZIP_KEY, zip_address)

        return context

    @classmethod
    def _address(cls, args: list[str]) -> Optional[str]:
        """Choose the explicit repository, or the official one when absent."""
        position = args.index(cls.SELECTOR_FLAG)
        if position + 1 == len(args):
            return cls.DEFAULT_REPOSITORY

        address = args[position + 1].strip()
        if not address or address.startswith("--"):
            return None
        return address
