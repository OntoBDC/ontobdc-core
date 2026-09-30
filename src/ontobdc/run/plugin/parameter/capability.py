from typing import Any, Optional, Tuple

from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.shared.domain.model.parameter import ParameterMetadata


class CapabilityIdStrategy(CliContextStrategyPort, RootPackagesAwarePort):
    """
    Resolve a capability identifier to an executable capability instance.

    The capability a user names is looked for wherever the executable
    running the command declares its plugins. An executable that reuses
    this runtime and registers capabilities of its own is told to the
    strategy, rather than assumed away: without that, ``run --capability``
    would answer only for the capabilities of the package this strategy
    lives in.
    """

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.ontobdc.run.plugin.parameter.capability_id",
        version="1.0.0",
        name="capability_id",
        description="Resolve a capability identifier to its plugin instance.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=Capability,
        tags=["run", "capability", "identifier"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(
        self,
        loader: Optional[CapabilityLoader] = None,
    ) -> None:
        self._loader: Optional[CapabilityLoader] = loader
        self._root_packages: Tuple[str, ...] = (
            CapabilityLoader.DEFAULT_ROOT_PACKAGES
        )

    def set_root_packages(self, root_packages: Tuple[str, ...]) -> None:
        """
        Discover capabilities in the packages the executable declares.
        """
        self._root_packages = root_packages

    def execute(self, context: CliContextPort) -> CliContextPort:
        capability_id: str = str(
            context.get_parameter_value("capability_id") or ""
        ).strip()
        if not capability_id:
            raise ValueError("Capability id cannot be empty.")

        capability_type: Any = self._capability_loader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Capability not found: {capability_id}")

        target_capability: Capability = capability_type()
        context.set_parameter_value(
            "target_capability",
            target_capability,
        )

        return context

    def _capability_loader(self) -> CapabilityLoader:
        """
        Return the loader to search with: the injected one, or one over the
        packages this strategy was told to discover in.
        """
        if self._loader is not None:
            return self._loader

        return CapabilityLoader(root_packages=self._root_packages)
