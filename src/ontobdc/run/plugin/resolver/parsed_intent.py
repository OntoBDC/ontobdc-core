import json
import os
from typing import Any, Dict, Optional
from ontobdc.cli import get_config_dir
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.shared.domain.port.context import CliContextPort


class ParsedIntentParamResolver:
    def resolve(self, context: CliContextPort, uri: str, prop: str) -> None:
        parsed_intent_file = os.path.join(
            get_config_dir(),
            IntentScoreResponse.PARSED_INTENT_FILE_NAME,
        )

        if not os.path.exists(parsed_intent_file):
            raise FileNotFoundError(
                f"Parsed intent file not found: {parsed_intent_file}"
            )

        with open(parsed_intent_file, "r", encoding="utf-8") as handle:
            parsed_intent: Optional[Dict[str, Any]] = json.load(handle) or {}

        if not isinstance(parsed_intent, dict):
            raise ValueError("Parsed intent file must contain a JSON object.")

        context.set_parameter_value(prop, IntentScoreResponse.load_from_jsonld(parsed_intent))
