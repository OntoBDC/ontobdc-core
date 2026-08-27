import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.plugin.capability.transformation.canonical import (
    CanonicalCapability,
)
from ontobdc.run.plugin.capability.transformation.low_confidence import (
    LowConfidenceCapability,
)
from ontobdc.run.plugin.capability.transformation.matched import MatchedCapability
from ontobdc.run.plugin.capability.transformation.parsed import ParsedCapability
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort

STATE_EXTENSION = "json"

_CHOICE_QUESTIONS: Dict[str, str] = {
    "en": "I found some possible capabilities. Which one do you want to use?",
    "pt": "Encontrei algumas capabilities possiveis. Qual voce quer usar?",
    "pt-br": "Encontrei algumas capabilities possiveis. Qual voce quer usar?",
    "pt-pt": "Encontrei algumas capabilities possiveis. Qual voce quer usar?",
}


class ValidatedCapability(TransformationCapability, PromptChoiceAwarePort):
    """Confirm, with the user, which matched capability the prompt meant.

    Reached two ways: from ``low_confidence`` once it resolved
    successfully, or from ``matched`` when the score was already
    sufficient. Either way, the state immediately upstream has already
    written a ``matching_capabilities`` list -- to ``__low_confidence__
    .json`` or ``__matched__.json`` respectively -- so this capability only
    has to read whichever one exists and ask the user to choose among it.
    The prompt text itself (only needed here for the ``__validated__.json``
    output's own ``prompt`` field) is read straight from ``received``'s
    state file, not from ``context``.

    Adapted from ``run/old/plugin/capability/resolution_to_validated.py``,
    which only handled the low-confidence path (it always read a
    matching-capabilities list that, in the original design, was only ever
    populated by the low-confidence step) -- ``matched`` is this version's
    equivalent state for the high-confidence path, closing that gap.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "validated"
        ),
        version="1.0.0",
        name="Validated Intent",
        description=(
            "Confirm, with the user, which matched capability the prompt "
            "meant."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "intent", "validated"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._prompt_choice: Optional[Callable[..., str]] = None
        self._selected_capability_id: Optional[str] = None

    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        self._prompt_choice = prompt_choice

    @property
    def metadata(self) -> CapabilityMetadata:
        # Same reasoning as the other run capabilities: log_message is
        # static text, so the resolved value is interpolated here, after
        # execute() has set _selected_capability_id.
        if self._selected_capability_id is None:
            return self.METADATA

        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"Validated capability: {self._selected_capability_id}.",
                        "pt-br": f"Capability validada: {self._selected_capability_id}.",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.VALIDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.VALIDATED.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort) -> Path:
        return ParsedCapability.state_directory(context)

    @classmethod
    def state_path(cls, context: CliContextPort) -> Path:
        return cls.state_directory(context) / (
            f"{IntentResolutionState.VALIDATED.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort) -> bool:
        try:
            path = self.state_path(context)
            if not path.is_file():
                return False
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(payload, dict) and bool(
                payload.get("selected_capability_id")
            )
        except (OSError, ValueError):
            return False

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if self._prompt_choice is None:
            raise RuntimeError("Prompt choice function is not configured.")

        received_path: Path = CanonicalCapability.received_state_path(context)
        if not received_path.is_file():
            raise ValueError(
                "No received prompt state file found; 'received' must "
                "run first."
            )
        prompt: str = received_path.read_text(encoding="utf-8").strip()
        if not prompt:
            raise ValueError(
                "No prompt available; 'received' must run first."
            )

        matching_capability_ids: List[str] = self._resolve_matching_capability_ids(
            context
        )
        if not matching_capability_ids:
            raise ValueError(
                f"The prompt '{prompt}' has no matching capabilities to "
                "validate against."
            )

        all_capabilities: List[Type[CapabilityPort]] = CapabilityLoader().get_all(
            "capability"
        )
        matching_capabilities: List[Type[CapabilityPort]] = [
            candidate
            for candidate in all_capabilities
            if candidate.METADATA.id in matching_capability_ids
        ]
        if not matching_capabilities:
            raise ValueError(
                "Matching capabilities were recorded but are no longer "
                "found by the capability loader."
            )

        language: str = str(context.language or "en").strip().lower()
        question: str = _CHOICE_QUESTIONS.get(language, _CHOICE_QUESTIONS["en"])
        choice_options: List[str] = [
            candidate().label(language) for candidate in matching_capabilities
        ]

        selected_label: str = self._prompt_choice(
            question, choice_options, language=language
        )
        selected_index: int = choice_options.index(selected_label)
        selected_capability: Type[CapabilityPort] = matching_capabilities[selected_index]
        selected_capability_id: str = selected_capability.METADATA.id

        state_path: Path = self.state_path(context)
        if not self.is_satisfied(context):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "prompt": prompt,
                        "matching_capabilities": matching_capability_ids,
                        "selected_capability_id": selected_capability_id,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._selected_capability_id = selected_capability_id
        return {
            "selected_capability_id": selected_capability_id,
            "matching_capabilities": matching_capability_ids,
            "state_path": str(state_path),
        }

    @staticmethod
    def _resolve_matching_capability_ids(context: CliContextPort) -> List[str]:
        for state_path in (
            LowConfidenceCapability.state_path(context),
            MatchedCapability.state_path(context),
        ):
            if not state_path.is_file():
                continue

            payload: Any = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                matches: Any = payload.get("matching_capabilities")
                if isinstance(matches, list):
                    return [str(match) for match in matches]

        return []
