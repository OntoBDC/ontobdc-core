from pathlib import Path

import yaml

from ontobdc.view.adapter.machine import _CAPABILITY_ID_BY_STATE
from ontobdc.view.domain.machine.state import ContainerViewProcessState


def test_facades_serialized_state_precedes_generated() -> None:
    states = list(ContainerViewProcessState)

    assert states.index(
        ContainerViewProcessState.FACADES_SERIALIZED
    ) == states.index(ContainerViewProcessState.GENERATED) - 1
    assert _CAPABILITY_ID_BY_STATE[
        ContainerViewProcessState.FACADES_SERIALIZED
    ].endswith(".facades_serialized")


def test_statechart_routes_hardcoded_through_facades_serialized() -> None:
    statechart_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ontobdc"
        / "view"
        / "domain"
        / "machine"
        / "standard_container_view.yaml"
    )
    document = yaml.safe_load(statechart_path.read_text(encoding="utf-8"))
    states = document["statechart"]["root state"]["states"]
    by_name = {state["name"]: state for state in states}

    assert by_name["hardcoded"]["transitions"][0]["target"] == (
        "facades_serialized"
    )
    assert by_name["facades_serialized"]["transitions"][0]["target"] == (
        "generated"
    )
