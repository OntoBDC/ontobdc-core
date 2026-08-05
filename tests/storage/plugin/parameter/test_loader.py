from ontobdc.shared.adapter.loader import ParameterLoader
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy


def test_parameter_loader_discovers_container_id_strategy() -> None:
    strategies = ParameterLoader().get_all()

    assert any(
        isinstance(strategy, ContainerIdStrategy)
        for strategy in strategies
    )
