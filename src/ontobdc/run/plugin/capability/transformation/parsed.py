import json
from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.adapter.spacy import SpacyIntentModelResolver
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.plugin.capability.transformation.canonical import (
    CanonicalCapability,
)
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

STATE_EXTENSION = "json"


class ParsedCapability(TransformationCapability):
    """Parse the canonical intent with spaCy (POS tags, entities,
    dependencies, root token(s)) and score it.

    Lands as a sibling of ``__received__.txt``/``__canonical__.json`` in
    ``received``'s per-prompt ETL directory (located via
    ``CanonicalCapability.state_directory``, itself just a lookup of the
    ``run_state_directory`` the handler lends down -- see
    ``CanonicalCapability``'s own docstring), since parsing operates on
    that same prompt's canonical text, read directly from
    ``__canonical__.json`` rather than from ``context``.

    The original design (``run/old/plugin/capability/resolution_to_parsed
    .py``) also raised a dedicated "language not supported" exception here.
    That case can no longer happen at this point in the chain:
    ``LanguageDefinedCapability`` already rejects an unrecognized language
    two states earlier, so by the time ``parsed`` runs the language is
    guaranteed to be one a3 (and therefore spaCy, via
    ``SpacyIntentModelResolver``) supports.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "parsed"
        ),
        version="1.0.0",
        name="Parsed Intent",
        description=(
            "Parse the canonical intent (POS tags, entities, dependencies, "
            "root) and score it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "intent", "parsed", "nlp"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._score: Optional[float] = None

    @property
    def metadata(self) -> CapabilityMetadata:
        # Same reasoning as the other run capabilities: log_message is
        # static text, so the resolved value is interpolated here, after
        # execute() has set _score.
        if self._score is None:
            return self.METADATA

        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"The prompt was parsed (score: {self._score}).",
                        "pt-br": f"O prompt foi analisado (pontuacao: {self._score}).",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.PARSED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.PARSED.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        return CanonicalCapability.state_directory(context)

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.PARSED.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort) -> bool:
        try:
            path = self.state_path(context)
            if not path.is_file():
                return False
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(payload, dict) and "score" in payload
        except (OSError, ValueError):
            return False

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        received_path: Path = CanonicalCapability.received_state_path(context)
        canonical_path: Path = CanonicalCapability.state_path(context)
        if not received_path.is_file() or not canonical_path.is_file():
            raise ValueError(
                "No canonical intent available to parse; 'received' and "
                "'canonical' must run first."
            )

        prompt: str = received_path.read_text(encoding="utf-8").strip()
        canonical_payload: Any = json.loads(canonical_path.read_text(encoding="utf-8"))
        canonical_intent: str = str(
            canonical_payload.get("canonical_intent")
            if isinstance(canonical_payload, dict)
            else ""
        ).strip()
        if not prompt or not canonical_intent:
            raise ValueError(
                "No canonical intent available to parse; 'received' and "
                "'canonical' must run first."
            )

        resolver = SpacyIntentModelResolver(context.language)
        parsed: Dict[str, Any] = resolver.parse(canonical_intent)

        state_path: Path = self.state_path(context)
        if not self.is_satisfied(context):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {"prompt": prompt, **parsed},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._score = parsed["score"]
        return {
            "score": parsed["score"],
            "entities": parsed["entities"],
            "roots": parsed["roots"],
            "state_path": str(state_path),
        }
