from enum import Enum


class DocumentImportProcessState(str, Enum):
    """
    General lifecycle states for importing documents and other information
    artifacts, transforming their contents into semantic instances, and
    publishing the resulting information inside an OntoBDC container.

    The states describe the maturity of the imported information rather than
    the implementation used to process it. Document-specific capabilities may
    therefore process schedules, reports, risk assessments, photographs,
    spreadsheets, BIM models, or other sources through the same lifecycle.
    """

    UNDEFINED = "__undefined__"

    # Acquisition
    INGESTED = "__ingested__"
    PROFILED = "__profiled__"

    # Interpretation
    EXTRACTED = "__extracted__"
    STRUCTURED = "__structured__"

    # Semantic transformation
    INSTANTIATED = "__instantiated__"
    RESOLVED = "__resolved__"
    VALIDATED = "__validated__"

    # Integration and publication
    LINKED = "__linked__"
    PACKAGED = "__packaged__"
    PUBLISHED = "__published__"

    # Exceptional and terminal states
    REVIEW_REQUIRED = "__review_required__"
    UNSUPPORTED = "__unsupported__"
    REJECTED = "__rejected__"
    FAILED = "__failed__"
    CANCELLED = "__cancelled__"
    SUPERSEDED = "__superseded__"

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.INGESTED: "Ingested",
                self.PROFILED: "Profiled",
                self.EXTRACTED: "Extracted",
                self.STRUCTURED: "Structured",
                self.INSTANTIATED: "Instantiated",
                self.RESOLVED: "Resolved",
                self.VALIDATED: "Validated",
                self.LINKED: "Linked",
                self.PACKAGED: "Packaged",
                self.PUBLISHED: "Published",
                self.REVIEW_REQUIRED: "Review Required",
                self.UNSUPPORTED: "Unsupported",
                self.REJECTED: "Rejected",
                self.FAILED: "Failed",
                self.CANCELLED: "Cancelled",
                self.SUPERSEDED: "Superseded",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": {
                self.UNDEFINED: (
                    "Initial state assigned before the import process has "
                    "materialized, classified, or otherwise processed any "
                    "source artifact."
                ),
                self.INGESTED: (
                    "The source artifact has entered the import process and "
                    "has been preserved in its original form. Its identity, "
                    "content hash, file name, media type, size, origin, and "
                    "available provenance have been recorded. When applicable, "
                    "the original artifact is already registered as an ICDD "
                    "payload document, but its contents have not yet been "
                    "interpreted."
                ),
                self.PROFILED: (
                    "The source artifact has been technically and "
                    "documentarily characterized so that suitable processing "
                    "capabilities can be selected. Profiling may identify the "
                    "document type, format, generating application, language, "
                    "revision, page geometry, presence of native text, scanned "
                    "content, tables, images, vector graphics, annotations, or "
                    "other relevant structural features. No domain assertions "
                    "are created solely from this characterization."
                ),
                self.EXTRACTED: (
                    "Observable content has been recovered from the source "
                    "without yet assigning domain meaning to it. Extracted "
                    "material may include text, words, bounding boxes, blocks, "
                    "tables, images, vector elements, metadata, bookmarks, "
                    "annotations, or OCR results. Every extracted fragment "
                    "should retain enough provenance to identify its source "
                    "artifact, page or region, and extraction method."
                ),
                self.STRUCTURED: (
                    "Extracted fragments have been organized into a coherent "
                    "intermediate representation that is independent of the "
                    "target ontology. Examples include rows, columns, cells, "
                    "sections, fields, records, candidate activities, dates, "
                    "relationships, risks, controls, or other document-level "
                    "structures. Each structured value remains traceable to "
                    "the evidence from which it was derived."
                ),
                self.INSTANTIATED: (
                    "The intermediate records have been transformed into "
                    "semantic instances and assertions according to the "
                    "selected domain models. For example, schedule records may "
                    "produce work schedules, tasks, task times, decompositions, "
                    "and sequence relationships, while other documents may "
                    "produce people, organizations, locations, requirements, "
                    "risks, controls, inspections, or occurrences. References "
                    "may still be unresolved at this stage."
                ),
                self.RESOLVED: (
                    "References and candidate identities have been reconciled "
                    "with known entities within the current import, the ICDD "
                    "container, previous revisions, or authorized external "
                    "datasets. Each attempted resolution should explicitly "
                    "record whether it is resolved, ambiguous, unresolved, or "
                    "conflicting, together with its supporting evidence, so "
                    "that uncertain correspondences are not silently asserted."
                ),
                self.VALIDATED: (
                    "The semantic instances, values, and relationships have "
                    "been checked for structural, referential, and domain "
                    "consistency. Validation may include schema conformance, "
                    "data types, cardinalities, SHACL shapes, temporal rules, "
                    "referential integrity, document-specific constraints, "
                    "completeness requirements, and cross-record consistency. "
                    "The validation result and every warning or violation are "
                    "recorded as auditable process outputs."
                ),
                self.LINKED: (
                    "Semantic instances have been connected to source "
                    "documents, exact document fragments, other semantic "
                    "entities, and relevant external artifacts. The resulting "
                    "ICDD RDF linksets may relate an entity to a complete "
                    "document, a page or bounding-box evidence fragment, "
                    "another entity such as an IFC object, or operational "
                    "records such as photographs, reports, permits, and risk "
                    "assessments."
                ),
                self.PACKAGED: (
                    "The original payloads and all selected process products "
                    "have been assembled into an ICDD container. The package "
                    "may include semantic models, human-editable "
                    "representations, RDF linksets, validation reports, "
                    "provenance, manifests, hashes, and capability versions. "
                    "The container is complete enough for final verification "
                    "but has not yet been declared an immutable published "
                    "version."
                ),
                self.PUBLISHED: (
                    "The ICDD container has passed final verification and has "
                    "been closed as an identifiable, immutable, and "
                    "distributable version. Final hashes, version identifiers, "
                    "and signatures, when applicable, have been recorded. Any "
                    "subsequent change must produce a new process execution or "
                    "container revision rather than silently altering the "
                    "published result."
                ),
                self.REVIEW_REQUIRED: (
                    "Automated processing completed far enough to produce "
                    "usable intermediate or semantic results, but one or more "
                    "ambiguities, low-confidence interpretations, unresolved "
                    "references, or validation findings require an explicit "
                    "human decision before normal processing can continue. "
                    "This is a controlled workflow state, not a technical "
                    "failure."
                ),
                self.UNSUPPORTED: (
                    "The artifact was ingested and profiled, but no available "
                    "adapter or processing capability can reliably handle its "
                    "format, structure, protection mechanism, or document type. "
                    "The source and profiling evidence remain preserved so "
                    "that processing may be retried when appropriate support "
                    "becomes available."
                ),
                self.REJECTED: (
                    "Processing produced interpretable results, but the source "
                    "or resulting semantic content does not satisfy the "
                    "minimum acceptance criteria required for integration or "
                    "publication. Rejection is a deliberate semantic or "
                    "governance decision supported by recorded validation "
                    "findings, not an unexpected execution error."
                ),
                self.FAILED: (
                    "The process could not complete the current operation "
                    "because of an unexpected technical error, unavailable "
                    "dependency, corrupted intermediate artifact, or other "
                    "execution failure. The failure context, completed states, "
                    "and recoverable outputs should be retained to support "
                    "diagnosis and safe retry."
                ),
                self.CANCELLED: (
                    "The import process was deliberately stopped before "
                    "publication by a user, an authorized workflow, or a "
                    "controlling process. Already materialized artifacts and "
                    "provenance are retained according to policy, but the "
                    "execution is not considered a completed semantic import."
                ),
                self.SUPERSEDED: (
                    "The process result or published container version has been "
                    "replaced by a newer accepted revision. The superseded "
                    "result remains identifiable and auditable and may still "
                    "be referenced for historical or provenance purposes, but "
                    "it is no longer the current authoritative version."
                ),
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ElementImportProcessState":
        return getattr(ElementImportProcessState, state.upper())
