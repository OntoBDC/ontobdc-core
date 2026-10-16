from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sismic.exceptions import CodeEvaluationError

import ontobdc.cli
from ontobdc.context.plugin.command.entity import ContextEntityInspectCommand
from ontobdc.context.plugin.machine.entity_inspection.machine import EntityInspectionStateTransitionHandler
from ontobdc.context.plugin.machine.entity_inspection.state import EntityInspectionProcessState


def context_for(entity_id):
    values = {"entity_id": entity_id}
    context = MagicMock()
    context.has_parameter.side_effect = lambda key: key in values
    context.get_parameter_value.side_effect = values.get
    context.set_parameter_value.side_effect = lambda key, value: values.__setitem__(key, value)
    return context, values


def test_command_delegates_to_fsm_and_preserves_response():
    context, values = context_for("urn:entity:one")
    facade = {"entity_iri": "urn:entity:one", "identifier": "one", "fields": []}
    command = ContextEntityInspectCommand(SimpleNamespace(context=context))
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info", return_value=facade) as lookup:
        response = command.run()
    lookup.assert_called_once_with("urn:entity:one")
    assert response.title == "Context Entity Inspect"
    assert response.description == "Facade of the entity <urn:entity:one>."
    assert response.content == facade
    assert values["entity_information"] == facade


def test_missing_facade_never_completes_the_state():
    context, values = context_for("urn:missing")
    handler = EntityInspectionStateTransitionHandler(context)
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info", return_value=None):
        with pytest.raises(CodeEvaluationError, match="urn:missing") as error:
            handler.execute()
    assert isinstance(error.value.__cause__, LookupError)
    assert handler.observed_state == EntityInspectionProcessState.ENTITY_URI_RESOLVED
    assert "entity_information" not in values


def test_previous_entity_information_is_not_reused_for_another_entity():
    context, values = context_for("urn:new")
    values["entity_information"] = {"entity_iri": "urn:old", "identifier": "old", "fields": []}
    facade = {"entity_iri": "urn:new", "identifier": "new", "fields": []}
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info", return_value=facade) as lookup:
        handler = EntityInspectionStateTransitionHandler(context)
        assert handler.execute().content == facade
    lookup.assert_called_once_with("urn:new")
    assert handler.current_state == EntityInspectionProcessState.ENTITY_INFORMATION_FOUND


def test_machine_resolves_the_uri_before_fetching_information():
    from ontobdc.context.plugin.machine.entity_inspection.machine import EntityInspectionStateEvaluatorAdapter
    assert EntityInspectionStateEvaluatorAdapter._state_sequence() == ["undefined", "entity_uri_resolved", "entity_information_found"]


@pytest.mark.parametrize("name", ["annotation", "Annotation", "ANOTAÇÃO", "anotacao"])
def test_resolves_alias_before_lookup(name):
    context, values = context_for(name)
    uri = "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation"
    facade = {"entity_iri": uri, "identifier": "annotation", "fields": []}
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info", return_value=facade) as lookup:
        assert EntityInspectionStateTransitionHandler(context).execute().content == facade
    lookup.assert_called_once_with(uri)
    assert values["entity_uri"] == uri
    assert values["entity_id"] == name


def test_unknown_name_stops_before_information_lookup():
    context, values = context_for("unknown entity")
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info") as lookup:
        with pytest.raises(CodeEvaluationError, match="No URI is registered"):
            EntityInspectionStateTransitionHandler(context).execute()
    lookup.assert_not_called()
    assert "entity_information" not in values


def test_no_entity_selector_still_lists_all_entities():
    context, values = context_for(None)
    values["entity_uri"] = "urn:stale"
    with patch("ontobdc.context.plugin.capability.transformation.entity_information_found.entity_info", return_value=[]) as lookup:
        assert EntityInspectionStateTransitionHandler(context).execute().content == []
    lookup.assert_called_once_with()
    assert values["entity_uri"] is None
