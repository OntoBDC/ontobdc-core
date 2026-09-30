from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, ClassVar, Dict, Optional

from rdflib import Graph, Namespace
from rdflib.namespace import SDO

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.domain.port.typification import FileTypificationStrategyPort


class ExtensionFileTypificationStrategy(FileTypificationStrategyPort):
    """
    Types a file by its extension.

    The extension-to-type knowledge lives in the OntoBDC typification
    ontology (``tbox/typification.ttl`` + ``abox/typification.ttl``,
    resolved from the ``brasidatacenter`` ontology tree through
    ``OntologyConfigAdapter``), not in a Python literal: which format
    types as what is domain knowledge the ontology owns, and this
    strategy only asks it, the same way a capability asks a
    ``ParamResolverStrategyPort`` instead of hardcoding how to resolve
    its own input.
    """

    URI: ClassVar[str] = "org.ontobdc.context.plugin.typification.extension"

    TBOX_PREFIX: ClassVar[str] = "obdc_tbox_typ"
    ABOX_PREFIX: ClassVar[str] = "obdc_abox_typ"
    ONTOLOGY_TYPE: ClassVar[str] = "typification"
    TYPIFICATION_NAMESPACE: ClassVar[Namespace] = Namespace(
        "http://datacenter.app.br/ontology/tool/ontobdc/tbox/typification.ttl#"
    )

    UNKNOWN_TYPE: ClassVar[str] = "unknown"
    UNKNOWN_SCORE: ClassVar[int] = 0
    KNOWN_EXTENSION_SCORE: ClassVar[int] = 1

    @property
    def uri(self) -> str:
        """
        Stable identifier for this strategy, keying its evaluation.
        """
        return self.URI

    def evaluate(self, source_path: str, mime: Optional[str]) -> Dict[str, Any]:
        """
        Return this strategy's typing of the file.
        """
        file_type: Optional[str] = self._type_by_extension().get(
            self._extension_of(source_path)
        )
        if file_type is None:
            return {
                self.TYPE_KEY: self.UNKNOWN_TYPE,
                self.SCORE_KEY: self.UNKNOWN_SCORE,
            }

        return {
            self.TYPE_KEY: file_type,
            self.SCORE_KEY: self.KNOWN_EXTENSION_SCORE,
        }

    @classmethod
    @lru_cache(maxsize=1)
    def _type_by_extension(cls) -> Dict[str, str]:
        """
        Return every extension the typification ontology declares, mapped
        to the ``schema:identifier`` of the artifact type it is typed as.

        Parsed once per process: the ontology changes only when the
        ``brasidatacenter`` tree it lives in changes, never between two
        files evaluated in the same run.
        """
        graph: Graph = Graph()
        ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
            config_adapter=UnsetProjectRootConfigDataAdapter(),
        )
        graph.parse(
            ontology_adapter.get_ontology_path(cls.TBOX_PREFIX, cls.ONTOLOGY_TYPE),
            format="turtle",
        )
        graph.parse(
            ontology_adapter.get_ontology_path(cls.ABOX_PREFIX, cls.ONTOLOGY_TYPE),
            format="turtle",
        )

        type_by_extension: Dict[str, str] = {}
        format_individual: Any
        artifact_type: Any
        for format_individual, artifact_type in graph.subject_objects(
            cls.TYPIFICATION_NAMESPACE.isTypeOf
        ):
            type_identifier: Any = graph.value(artifact_type, SDO.identifier)
            if type_identifier is None:
                continue

            extension: Any
            for extension in graph.objects(format_individual, SDO.identifier):
                type_by_extension[str(extension).strip().lower()] = str(
                    type_identifier
                )

        return type_by_extension

    @staticmethod
    def _extension_of(source_path: str) -> str:
        return PurePosixPath(source_path).suffix.lstrip(".").lower()
