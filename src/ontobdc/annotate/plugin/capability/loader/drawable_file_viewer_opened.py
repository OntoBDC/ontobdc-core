from typing import ClassVar, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.mime_chain_capability import MimeChainExecution
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.port import (
    DrawableFileViewerChainSupport,
)


class DrawableFileViewerOpenedCapability(
    TransactionCapability,
    RootPackagesAwarePort,
):
    """
    Open the viewer that matches the kind of the requested file.

    The capability the request maps explicitly to the MIME type of the file
    runs directly. When it maps none, the chain of responsibilities runs, and
    the responsibilities that accept the file open their viewer. A file
    nobody opens is an error. What the capabilities that did the opening
    returned, by capability id, is the result; the viewer session that must
    reach the next state stays in the context, where the responsibility put
    it.
    """

    CHAIN_PACKAGE: ClassVar[str] = (
        "ontobdc.annotate.plugin.machine.annotation_creation_from_point"
    )
    CHAIN_FILE: ClassVar[str] = "standard_drawable_file_viewer_chain.yaml"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.loader."
            "drawable_file_viewer_opened"
        ),
        version="1.0.0",
        name="Drawable File Viewer Opened",
        description=(
            "Open the viewer of the requested file with the capability "
            "mapped to its MIME type or, failing that, with the chain "
            "responsibilities that accept it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "drawing", "chain", "viewer", "loader"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                DrawableFileViewerChainSupport.PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={"properties": {}},
    )

    def __init__(self) -> None:
        self._root_packages: Tuple[str, ...] = ("ontobdc",)

    def set_root_packages(self, root_packages: Tuple[str, ...]) -> None:
        self._root_packages = root_packages or ("ontobdc",)

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Visualizador do arquivo desenhável aberto"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        return MimeChainExecution.execute(
            context,
            DrawableFileViewerChainSupport,
            DrawableFileViewerChainSupport.CAPABILITY_BY_MIME_KEY,
            self.CHAIN_PACKAGE,
            self.CHAIN_FILE,
            self._root_packages,
            (
                "No drawable-file-viewer capability is registered for the file's MIME type and no drawable-file-viewer chain responsibility opened"
            ),
        )
