import json
import re
import string
from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.plugin.capability.transformation.received import (
    STATE_EXTENSION as RECEIVED_STATE_EXTENSION,
)
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

STATE_EXTENSION = "json"

_WHITESPACE_RE = re.compile(r"\s+")

_RUN_STATE_DIRECTORY_PARAMETER = "run_state_directory"


class CanonicalCapability(TransformationCapability):
    """Normalize the received prompt into a stable canonical form.

    Lands as a sibling file in ``received``'s own per-prompt ETL directory
    -- ``.__ontobdc__/etl/run/<hash>/{__received__.txt, __canonical__.json}``
    -- mirroring how multiple states of the same DataGatheredCapability
    pipeline share one container-scoped ETL directory. That directory is
    handed down by the handler (see ``IntentResolutionStateTransitionHandler
    .perform_state_transition``) as ``run_state_directory``, computed once
    from ``received``'s own result -- this capability locates it that way
    rather than re-hashing the prompt text itself, and reads the prompt's
    actual text straight from ``received``'s state file, not from
    ``context`` (only ``received`` itself, which has no prior state file to
    read from, legitimately takes the prompt via ``context``).

    Normalization is deliberately lightweight for now (lowercase, collapse
    whitespace, strip surrounding punctuation) rather than the spaCy
    lemmatization + spell-correction the original design sketched
    (``run/old/plugin/capability/resolution_to_canonical.py``): no spaCy
    language model is downloaded in this environment, and pulling one in
    is a real, sizeable network operation that shouldn't happen as a side
    effect of this change. The ETL contract (a JSON file with a
    ``canonical_intent`` key) is the same either way, so swapping the
    normalization internals for real NLP later doesn't ripple outward.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "canonical"
        ),
        version="1.0.0",
        name="Canonical Intent",
        description=(
            "Normalize the received prompt into a stable canonical form."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "intent", "canonical"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._canonical_intent: Optional[str] = None

    @property
    def metadata(self) -> CapabilityMetadata:
        # Same reasoning as PromptReceivedCapability/LanguageDefinedCapability:
        # log_message is static text, so the resolved value is interpolated
        # here, after execute() has set _canonical_intent.
        if self._canonical_intent is None:
            return self.METADATA

        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"The prompt was canonicalized: {self._canonical_intent}",
                        "pt-br": f"O prompt foi canonicalizado: {self._canonical_intent}",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.CANONICAL.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.CANONICAL.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        run_state_directory: str = str(
            context.get_parameter_value(_RUN_STATE_DIRECTORY_PARAMETER) or ""
        ).strip()
        if not run_state_directory:
            raise ValueError(
                "No run state directory available; the 'received' state "
                "must run first."
            )
        return Path(run_state_directory)

    @classmethod
    def received_state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.RECEIVED.value}.{RECEIVED_STATE_EXTENSION}"
        )

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.CANONICAL.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort) -> bool:
        try:
            path = self.state_path(context)
            if not path.is_file():
                return False
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(payload, dict) and bool(payload.get("canonical_intent"))
        except (OSError, ValueError):
            return False

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        received_path: Path = self.received_state_path(context)
        if not received_path.is_file():
            raise ValueError(
                "No received prompt state file found; the 'received' "
                "state must run first."
            )
        prompt: str = received_path.read_text(encoding="utf-8").strip()
        if not prompt:
            raise ValueError(
                "No prompt available to canonicalize; the 'received' "
                "state must run first."
            )

        canonical_intent: str = self._canonicalize(prompt)

        state_path: Path = self.state_path(context)
        if not self.is_satisfied(context):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {"prompt": prompt, "canonical_intent": canonical_intent},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._canonical_intent = canonical_intent
        return {"canonical_intent": canonical_intent, "state_path": str(state_path)}

    @staticmethod
    def _canonicalize(prompt: str) -> str:
        normalized: str = _WHITESPACE_RE.sub(" ", prompt.strip().lower())
        return normalized.strip(string.punctuation + " ")
