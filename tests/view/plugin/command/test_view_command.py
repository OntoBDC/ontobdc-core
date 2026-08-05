from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy
from ontobdc.view.plugin.command.view import ContainerViewCommand


class FakeContext:
    def __init__(
        self,
        raw_args: Optional[List[str]] = None,
        **parameters: Any,
    ) -> None:
        self._parameters: Dict[str, Any] = dict(parameters)
        if raw_args is not None:
            self.raw_args = raw_args

    def get_parameter_value(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def has_parameter(self, name: str) -> bool:
        return name in self._parameters


def test_view_command_argument_matching() -> None:
    assert ContainerViewCommand.accepts(["view"])
    assert ContainerViewCommand.accepts(
        ["view", "--container", ".", "--language", "pt-br"]
    )
    assert not ContainerViewCommand.accepts(
        [
            "view",
            "--container",
            ".",
            "--container-id",
            "urn:container",
        ]
    )
    assert not ContainerViewCommand.accepts(["view", "--language"])


def test_container_strategy_binds_deepest_registered_container(
    tmp_path: Path,
    monkeypatch,
) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    selected = inner / "documents"
    selected.mkdir(parents=True)

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(
            lambda _root_path=None: (
                ("urn:outer", outer),
                ("urn:inner", inner),
            )
        ),
    )

    context = FakeContext(container=str(selected))
    ContainerIdStrategy().execute(context)

    assert context.get_parameter_value("container_id") == "urn:inner"
    assert Path(context.get_parameter_value("container_path")) == inner


def test_container_strategy_ignores_stale_persisted_selector(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container = tmp_path / "current"
    working_directory = container / "documents"
    working_directory.mkdir(parents=True)

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(lambda _root_path=None: (("urn:current", container),)),
    )
    monkeypatch.chdir(working_directory)

    context = FakeContext(
        raw_args=[],
        container_id="urn:stale",
        container_path=str(tmp_path / "stale"),
    )
    ContainerIdStrategy().execute(context)

    assert context.get_parameter_value("container_id") == "urn:current"
    assert Path(context.get_parameter_value("container_path")) == container


def test_view_command_resolves_container_from_current_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container = tmp_path / "techcenter-doc"
    working_directory = container / "documents"
    working_directory.mkdir(parents=True)
    container_id = "urn:ontobdc:storage/local/techcenter-doc"

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(lambda _root_path=None: ((container_id, container),)),
    )
    monkeypatch.chdir(working_directory)

    context = FakeContext(raw_args=[])
    request = SimpleNamespace(context=context, command_args=[])
    command = ContainerViewCommand(request)

    assert command.check()
    assert context.get_parameter_value("container_id") == container_id
    assert Path(context.get_parameter_value("container_path")) == container


def test_container_strategy_resolves_local_container_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container = tmp_path / "techcenter-doc"
    working_directory = container / "documents"
    config_directory = container / ".__ontobdc__"
    working_directory.mkdir(parents=True)
    config_directory.mkdir()
    container_id = "urn:ontobdc:storage/local/techcenter-doc"
    container_uri = container.resolve().as_uri()

    (config_directory / "container.ttl").write_text(
        (
            "@prefix dcterms: <http://purl.org/dc/terms/> .\n"
            "@prefix obdc: "
            "<http://ontobdc.org/ontology/domain/ns.ttl#> .\n"
            "@prefix prov: <http://www.w3.org/ns/prov#> .\n\n"
            f"<{container_id}> a obdc:DataContainer ;\n"
            f'    dcterms:identifier "{container_id}" ;\n'
            f"    prov:atLocation <{container_uri}> .\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ContainerIdStrategy,
        "_registered_containers",
        staticmethod(lambda _root_path=None: ()),
    )
    monkeypatch.chdir(working_directory)

    context = FakeContext(raw_args=[])
    request = SimpleNamespace(context=context, command_args=[])
    command = ContainerViewCommand(request)

    assert command.check()
    assert context.get_parameter_value("container_id") == container_id
    assert Path(context.get_parameter_value("container_path")) == container
