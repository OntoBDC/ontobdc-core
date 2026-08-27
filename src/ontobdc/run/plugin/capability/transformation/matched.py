import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.plugin.capability.transformation.canonical import (
    CanonicalCapability,
)
from ontobdc.run.plugin.capability.transformation.low_confidence import (
    LowConfidenceCapability,
)
from ontobdc.run.plugin.capability.transformation.parsed import ParsedCapability
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

STATE_EXTENSION = "json"


class MatchedCapability(TransformationCapability):
    """Resolve candidate capabilities by tag directly from a sufficiently
    -scored parsed intent's single noun root.

    This is ``low_confidence``'s counterpart for the high-confidence path:
    when ``parsed`` already cleared the score threshold, there is no
    ``low_confidence`` step to have found candidates along the way, so
    this state does that same tag-matching work before ``validated`` asks
    the user to choose among them. Reuses
    ``LowConfidenceCapability._find_matching_capability_ids`` rather than
    re-implementing the same tag-matching algorithm.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "matched"
        ),
        version="1.0.0",
        name="Matched Intent",
        description=(
            "Match candidate capabilities by tag from a sufficiently "
            "-scored parsed intent."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "intent", "matched"],
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
                        "en": f"Matched by tag: {matches}.",
                        "pt-br": f"Correspondido por tag: {matches}.",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.MATCHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.MATCHED.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        return ParsedCapability.state_directory(context)

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.MATCHED.value}.{STATE_EXTENSION}"
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
                f"The prompt '{prompt}' has no single clear noun root to "
                "match by capability tag."
            )

        lemmas: Set[str] = {
            str(root.get("lemma", "")).strip().lower()
            for root in noun_roots
            if str(root.get("lemma", "")).strip()
        }

        matching_capability_ids: List[str] = (
            LowConfidenceCapability._find_matching_capability_ids(
                lemmas, context.language
            )
        )
        if not matching_capability_ids:
            raise ValueError(
                f"The prompt '{prompt}' could not be matched to any "
                "capability by tag."
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
