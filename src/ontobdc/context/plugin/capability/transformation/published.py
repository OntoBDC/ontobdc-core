import json
from datetime import datetime, timezone
from typing import Any, Dict

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, XSD

from ontobdc.context.adapter.repository import EntityLearningStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityLearningProcessState
from ontobdc.context.plugin.check.has_valid_context.hotfix import (
    main as hotfix_valid_context,
)
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort

BASE_CONTEXT_URI: Namespace = Namespace("urn:ontobdc:context/")
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


class PublishedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.published",
        version="1.0.0",
        name="Context learning transformation to Published",
        description="Publish the aligned learning result into context.ttl.",
        author=["TRAE"],
        tags=["context", "learning", "published"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Aligned learning result was published into the context graph."
                ),
            },
            "debug_entry": {
                "en": (
                    "Publishing the aligned learning result into the "
                    "context graph."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Context learning transformation to Published"

    def description(self, lang: str = "en") -> str:
        return "Publish the aligned learning result into context.ttl."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        entity_uri: str = str(context.get_parameter_value("entity_uri")).strip()
        root_path: str = str(context.root_path).strip()

        identified_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityLearningProcessState.IDENTIFIED).content)
        )
        aligned_payload: Dict[str, Any] = json.loads(
            str(step_repository.reload(EntityLearningProcessState.ALIGNED).content)
        )

        context_file_path = step_repository.step_dir.parents[3] / "context.ttl"
        if hotfix_valid_context(root_path=root_path) != 0:
            raise ValueError(f"Could not initialize context.ttl at '{context_file_path}'.")

        graph: Graph = Graph()
        graph.parse(context_file_path, format="turtle")
        graph.bind("", BASE_CONTEXT_URI)
        graph.bind("obdc", OBDC)
        graph.bind("owl", OWL)

        context_ref: URIRef = BASE_CONTEXT_URI["CurrentContext"]
        record_ref: URIRef = BASE_CONTEXT_URI[f"EntityLearningRecord/{step_repository.source_hash}"]
        record_type: URIRef = BASE_CONTEXT_URI["EntityLearningRecord"]
        has_record_predicate: URIRef = BASE_CONTEXT_URI["hasEntityLearningRecord"]
        entity_uri_predicate: URIRef = BASE_CONTEXT_URI["entityUri"]
        source_file_predicate: URIRef = BASE_CONTEXT_URI["sourceFile"]
        source_file_path_predicate: URIRef = BASE_CONTEXT_URI["sourceFilePath"]
        supported_file_type_predicate: URIRef = BASE_CONTEXT_URI["supportedFileType"]
        content_language_predicate: URIRef = BASE_CONTEXT_URI["contentLanguage"]
        language_score_predicate: URIRef = BASE_CONTEXT_URI["languageScore"]
        aligned_vector_predicate: URIRef = BASE_CONTEXT_URI["alignedVector"]
        trained_at_predicate: URIRef = BASE_CONTEXT_URI["learnedAt"]

        graph.remove((record_ref, None, None))
        graph.remove((context_ref, has_record_predicate, record_ref))
        graph.add((context_ref, has_record_predicate, record_ref))
        graph.add((record_ref, RDF.type, OWL.NamedIndividual))
        graph.add((record_ref, RDF.type, record_type))
        graph.add((record_ref, entity_uri_predicate, URIRef(entity_uri)))
        graph.add((record_ref, source_file_predicate, URIRef(identified_payload["uri"])))
        graph.add((record_ref, source_file_path_predicate, Literal(identified_payload["path"])))
        graph.add((record_ref, supported_file_type_predicate, Literal(identified_payload["mimetype"])))
        graph.add((record_ref, content_language_predicate, Literal(aligned_payload["language"]["code"])))
        graph.add(
            (
                record_ref,
                language_score_predicate,
                Literal(float(aligned_payload["language"]["score"]), datatype=XSD.decimal),
            )
        )
        graph.add(
            (
                record_ref,
                aligned_vector_predicate,
                Literal(json.dumps(aligned_payload["weight"], ensure_ascii=True)),
            )
        )
        graph.add(
            (
                record_ref,
                trained_at_predicate,
                Literal(datetime.now(timezone.utc).replace(microsecond=0).isoformat(), datatype=XSD.dateTime),
            )
        )
        graph.add((URIRef(entity_uri), supported_file_type_predicate, Literal(identified_payload["mimetype"])))
        graph.serialize(destination=context_file_path, format="turtle")

        published_payload: Dict[str, Any] = {
            "entity_uri": entity_uri,
            "source_file": identified_payload["path"],
            "supported_file_type": identified_payload["mimetype"],
            "language": dict(aligned_payload["language"]),
            "weight": list(aligned_payload["weight"]),
            "context_file": str(context_file_path),
            "record_uri": str(record_ref),
        }
        published_path = step_repository.write_text_file(
            state=EntityLearningProcessState.PUBLISHED,
            content=json.dumps(published_payload, ensure_ascii=True, indent=2, sort_keys=True),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(published_path))
        return {
            "resulting_state": EntityLearningProcessState.PUBLISHED,
            "path": str(published_path),
        }
