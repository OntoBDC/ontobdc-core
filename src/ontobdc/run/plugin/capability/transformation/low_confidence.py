import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.plugin.capability.transformation.canonical import (
    CanonicalCapability,
)
from ontobdc.run.plugin.capability.transformation.parsed import ParsedCapability
from ontobdc.shared.adapter.capability import (
    QueryCapability,
    TransactionCapability,
    TransformationCapability,
)
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort

STATE_EXTENSION = "json"


class LowConfidenceCapability(TransformationCapability):
    """Attempt to rescue an insufficiently-scored parsed intent by matching
    its single noun root's lemma against every registered capability's
    tags, before intent resolution would otherwise have to ask the user to
    reformulate the request.

    Adapted from ``run/old/plugin/capability/resolution_from_low_confidence
    .py``: that version re-ran spaCy on ``canonical_intent`` from scratch.
    Here ``parsed`` already parsed that same canonical text, so this reads
    its ``roots`` straight back out of the already-written
    ``__parsed__.json`` ETL artifact instead of parsing again.

    Known gap carried over unchanged from the original design: the
    ``TransformationCapabilityPort`` exclusion below only filters out
    *transformation* capabilities (this whole intent-resolution pipeline
    included) from the tag search -- a ``TransactionCapability`` like
    ``PromptReceivedCapability`` or this one is technically still eligible.
    In practice their tags (``run``, ``prompt``, ``intent``, ...) are
    unlikely to collide with a real task's noun lemma, so this wasn't
    tightened further.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "low_confidence"
        ),
        version="1.0.0",
        name="Low Confidence Intent Resolution",
        description=(
            "Suggest likely capabilities by tag when the parsed intent "
            "score is insufficient."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "intent", "low-confidence"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._matching_capability_ids: Optional[List[str]] = None

    @property
    def metadata(self) -> CapabilityMetadata:
        # Same reasoning as the other run capabilities: log_message is
        # static text, so the resolved value is interpolated here, after
        # execute() has set _matching_capability_ids.
        if self._matching_capability_ids is None:
            return self.METADATA

        matches: str = ", ".join(self._matching_capability_ids) or "none"
        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"Low-confidence intent matched by tag: {matches}.",
                        "pt-br": f"Intencao de baixa confianca correspondida por tag: {matches}.",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.LOW_CONFIDENCE.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.LOW_CONFIDENCE.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        return ParsedCapability.state_directory(context)

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.LOW_CONFIDENCE.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort) -> bool:
        try:
            path = self.state_path(context)
            if not path.is_file():
                return False
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(payload, dict) and bool(payload.get("matching_capabilities"))
        except (OSError, ValueError):
            return False

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        received_path: Path = CanonicalCapability.received_state_path(context)
        parsed_path: Path = ParsedCapability.state_path(context)
        if not received_path.is_file() or not parsed_path.is_file():
            raise ValueError(
                "No parsed intent available; 'received' and 'parsed' "
                "must run first."
            )

        prompt: str = received_path.read_text(encoding="utf-8").strip()
        parsed_payload: Any = json.loads(parsed_path.read_text(encoding="utf-8"))
        roots: List[Dict[str, Any]] = (
            parsed_payload.get("roots") if isinstance(parsed_payload, dict) else None
        ) or []

        noun_roots: List[Dict[str, Any]] = [
            root for root in roots if root.get("pos") == "NOUN"
        ]
        if not noun_roots or len(noun_roots) > 1:
            raise ValueError(
                f"The prompt '{prompt}' has an insufficient confidence "
                "score and no single clear noun root to resolve by "
                "capability tag matching."
            )

        lemmas: Set[str] = {
            str(root.get("lemma", "")).strip().lower()
            for root in noun_roots
            if str(root.get("lemma", "")).strip()
        }

        matching_capability_ids: List[str] = self._find_matching_capability_ids(
            lemmas, context.language
        )
        if not matching_capability_ids:
            raise ValueError(
                f"The prompt '{prompt}' could not be resolved to any "
                "capability by tag matching."
            )

        state_path: Path = self.state_path(context)
        if not self.is_satisfied(context):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "prompt": prompt,
                        "matching_capabilities": matching_capability_ids,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._matching_capability_ids = matching_capability_ids
        return {
            "matching_capabilities": matching_capability_ids,
            "state_path": str(state_path),
        }

    @staticmethod
    def _find_matching_capability_ids(lemmas: Set[str], language: str) -> List[str]:
        if not lemmas:
            return []

        matching_capability_ids: List[str] = []
        candidate_type: Type[CapabilityPort]
        for candidate_type in CapabilityLoader().get_all("capability"):
            if issubclass(candidate_type, TransformationCapability):
                continue
            if not issubclass(candidate_type, (QueryCapability, TransactionCapability)):
                continue

            try:
                candidate: CapabilityPort = candidate_type()
            except Exception:
                continue

            tags: Set[str] = {
                str(tag).strip().lower()
                for tag in candidate.tags(language)
                if str(tag).strip()
            }
            if lemmas.intersection(tags):
                matching_capability_ids.append(candidate.metadata.id)

        return matching_capability_ids
