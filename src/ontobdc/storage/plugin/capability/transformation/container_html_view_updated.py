import shutil
from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState


class ContainerHtmlViewUpdatedCapability(TransactionCapability):
    """Regenerate an existing root index.html through the view generation pipeline."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_html_view_updated"
        ),
        version="2.0.0",
        name="Updated Container HTML View",
        description=(
            "Regenerate an existing container index.html by re-running the same "
            "Surface generation pipeline used by 'ontobdc view'."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "view", "html"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        # Imported lazily: the view plugin depends on storage, so importing
        # it at module load time would create a circular import.
        from ontobdc.view.adapter.surface.machine import (
            SurfaceGenerationStateTransitionHandler,
        )
        from ontobdc.view.plugin.capability.transformation.data_gathered import (
            DataGatheredCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_datapackage_updated import (
            ContainerDataPackageUpdatedCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_ro_crate_updated import (
            ContainerRoCrateUpdatedCapability,
        )

        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        index_path: Path = container_path / "index.html"
        if not index_path.is_file():
            raise ValueError(
                "Container HTML view update was requested, but index.html does "
                f"not exist: {index_path}"
            )

        context.set_parameter_value(
            "view_type",
            context.get_parameter_value("view_type") or "standard",
        )
        context.set_parameter_value(
            "representation",
            context.get_parameter_value("representation") or "html",
        )
        context.set_parameter_value(
            "language",
            context.get_parameter_value("language") or "en",
        )

        # Same precautions as `ontobdc view`: drop the current index.html and
        # any leftover ETL state so the pipeline runs fresh instead of
        # resuming mid-state from a stale prior run.
        index_path.unlink()
        etl_state_directory: Path = DataGatheredCapability.state_directory(
            context
        )
        if etl_state_directory.is_dir():
            shutil.rmtree(etl_state_directory)

        SurfaceGenerationStateTransitionHandler(context=context).execute()

        if not index_path.is_file():
            raise ValueError(
                "The Surface generation pipeline finished without "
                f"regenerating {index_path}."
            )

        # The Surface generation pipeline can add or touch container
        # resources (e.g. RO-Crate/data package artifacts), which would
        # otherwise leave the container update statechart's earlier
        # Data Package/RO-Crate sync steps stale. Re-sync them here so the
        # observed state still reaches CONTAINER_HTML_VIEW_UPDATED.
        ContainerDataPackageUpdatedCapability().execute(context)
        ContainerRoCrateUpdatedCapability().execute(context)

        context.set_parameter_value("container_html_view_updated", True)

        return {
            "resulting_state": (
                ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED
            ),
            "container_path": str(container_path),
            "index_path": str(index_path),
        }
