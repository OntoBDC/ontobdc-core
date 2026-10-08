from typing import ClassVar, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.mime_chain_capability import MimeChainExecution
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.annotation.plugin.machine.annotation_creation_from_point.port import (
    AnnotationDetailsChainSupport,
)


class AnnotationDetailsFilledCapability(
    TransactionCapability,
    RootPackagesAwarePort,
):
    """
    Ask for the details of the annotations: title, text and author.

    The capability the request maps explicitly to the MIME type of the file
    runs directly. When it maps none, the chain of responsibilities runs, and
    the responsibilities that accept the file ask. A file nobody asks about
    is an error, and so is an answer without a title. The details stay in
    the context, under the keys of ``AnnotationDetailsChainSupport``, where
    the responsibility put them.
    """

    CHAIN_PACKAGE: ClassVar[str] = (
        "ontobdc.annotation.plugin.machine.annotation_creation_from_point"
    )
    CHAIN_FILE: ClassVar[str] = "standard_annotation_details_chain.yaml"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotation.plugin.capability.loader."
            "annotation_details_filled"
        ),
        version="1.0.0",
        name="Annotation Details Filled",
        description=(
            "Ask for the title, text and author of the annotations with the "
            "capability mapped to the MIME type of the file or, failing "
            "that, with the chain responsibilities that accept it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "drawing", "chain", "details", "loader"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                AnnotationDetailsChainSupport.PATH_KEY: {
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
            return "Detalhes da anotação preenchidos"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        results: Dict[str, Dict[str, object]] = MimeChainExecution.execute(
            context,
            AnnotationDetailsChainSupport,
            AnnotationDetailsChainSupport.CAPABILITY_BY_MIME_KEY,
            self.CHAIN_PACKAGE,
            self.CHAIN_FILE,
            self._root_packages,
            (
                "No annotation-details capability is registered for the file's "
                "MIME type and no annotation-details chain responsibility "
                "filled"
            ),
        )
        title: object = context.get_parameter_value(AnnotationDetailsChainSupport.TITLE_KEY)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("The annotation details were filled without a title.")

        return results
