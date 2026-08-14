from ontobdc.context.plugin.command.suggest import ContextSuggestCommand


def test_command_accepts_required_suggestion_contract():
    assert ContextSuggestCommand.accepts(
        [
            "context",
            "--entity",
            "WorkStream",
            "--global-id",
            "WS-001",
            "--dimension",
            "who",
            "--suggest",
        ]
    )


def test_command_rejects_contract_without_global_id():
    assert not ContextSuggestCommand.accepts(
        ["context", "--entity", "WorkStream", "--dimension", "who", "--suggest"]
    )
