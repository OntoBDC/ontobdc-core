import pytest

from ontobdc.context.adapter.suggestion_agent import (
    invoke_suggestion_agent,
    validate_suggestion_response,
)


def test_valid_suggestions_are_deduplicated_in_candidate_order():
    assert validate_suggestion_response(
        '{"suggested":["R003","R001","R003"]}',
        ["R001", "R002", "R003"],
    ) == ["R001", "R003"]


@pytest.mark.parametrize(
    "raw",
    [
        'answer: {"suggested":[]}',
        '{"suggested":["R999"]}',
        '{"suggested":[],"explanation":"x"}',
        '{"suggested":"R001"}',
    ],
)
def test_invalid_or_untrusted_outputs_fail_the_whole_operation(raw):
    with pytest.raises(ValueError):
        validate_suggestion_response(raw, ["R001"])


def test_empty_model_selection_is_valid():
    assert validate_suggestion_response('{"suggested":[]}', ["R001"]) == []


def test_missing_agent_cli_fails_explicitly(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError, match="installed 'codex' or 'claude' CLI"):
        invoke_suggestion_agent("prompt")
