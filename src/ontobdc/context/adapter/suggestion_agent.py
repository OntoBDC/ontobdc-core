import json
import shutil
import subprocess
from collections.abc import Iterable


def invoke_suggestion_agent(prompt: str) -> str:
    """Invoke an installed read-only selector CLI through stdin."""
    if shutil.which("codex"):
        command = ["codex", "exec", "--sandbox", "read-only", "-"]
    elif shutil.which("claude"):
        command = ["claude", "--print"]
    else:
        raise RuntimeError(
            "AI suggestion requires an installed 'codex' or 'claude' CLI."
        )
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"AI suggestion CLI invocation failed: {detail}")
    return completed.stdout


def validate_suggestion_response(raw: str, candidate_order: Iterable[str]) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response must be one JSON object with no prose.") from exc
    if not isinstance(payload, dict) or set(payload) != {"suggested"}:
        raise ValueError("AI response must contain only a 'suggested' array.")
    suggested = payload["suggested"]
    if not isinstance(suggested, list) or not all(
        isinstance(x, str) for x in suggested
    ):
        raise ValueError("AI response 'suggested' must be an array of strings.")
    known = list(candidate_order)
    unknown = sorted(set(suggested) - set(known))
    if unknown:
        raise ValueError(f"AI response contains unknown candidate keys: {unknown}")
    selected = set(suggested)
    return [key for key in known if key in selected]
