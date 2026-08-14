import sys
from pathlib import Path
from typing import List

import pytest

import ontobdc.cli  # noqa: F401 -- see loader.py's own note on this import ordering
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CommandLoader


@pytest.fixture
def fake_root_package(tmp_path: Path):
    """A synthetic installed package following ontobdc's own
    <domain>/plugin/<resource>/ convention, so CommandLoader(root_package=...)
    can be exercised without depending on a real downstream package (like
    infobim) being installed in this repo's own test environment.
    """
    package_name = "fake_ontobdc_downstream"
    package_dir = tmp_path / package_name
    (package_dir / "widgets" / "plugin" / "command").mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    (package_dir / "widgets" / "__init__.py").write_text("")
    (package_dir / "widgets" / "plugin" / "__init__.py").write_text("")
    (package_dir / "widgets" / "plugin" / "command" / "__init__.py").write_text("")
    (package_dir / "widgets" / "plugin" / "command" / "foo.py").write_text(
        "from ontobdc.cli.domain.model.command import CliCommandMetadata\n"
        "from ontobdc.cli.domain.port.command import CliCommandPort\n"
        "\n"
        "# A command imported from a different domain must not leak into\n"
        "# this domain's discovered list -- only its own declared\n"
        "# logical_component counts, not the directory it's found under.\n"
        "from ontobdc.cli.plugin.command.init import CliInitCommand\n"
        "\n"
        "\n"
        "class FooCommand(CliCommandPort):\n"
        "    METADATA = CliCommandMetadata(\n"
        "        id='foo', logical_component='widgets', description='',\n"
        "    )\n"
        "\n"
        "    @staticmethod\n"
        "    def accepts(args):\n"
        "        return args == ['widgets', '--foo']\n"
        "\n"
        "    def check(self):\n"
        "        return True\n"
        "\n"
        "    def run(self):\n"
        "        return None\n"
        "\n"
        "\n"
        "# A stale alias binding the same class under a second name must not\n"
        "# cause it to be listed twice.\n"
        "AliasedFooCommand = FooCommand\n"
    )

    sys.path.insert(0, str(tmp_path))
    try:
        yield package_name
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == package_name or module_name.startswith(f"{package_name}."):
                del sys.modules[module_name]


def test_command_loader_discovers_commands_from_a_non_ontobdc_root_package(fake_root_package: str) -> None:
    commands: List[type] = CommandLoader(
        "widgets", NullLogRepository(), root_package=fake_root_package
    ).get_all()

    assert len(commands) == 1
    assert commands[0].__name__ == "FooCommand"
    assert commands[0].METADATA.id == "foo"


def test_command_loader_excludes_commands_imported_from_another_domain(fake_root_package: str) -> None:
    commands = CommandLoader("widgets", NullLogRepository(), root_package=fake_root_package).get_all()

    # CliInitCommand (imported into foo.py, but METADATA.logical_component
    # == "cli") must not appear in the "widgets" domain's discovered list.
    assert all(command.METADATA.logical_component == "widgets" for command in commands)
    assert "CliInitCommand" not in [command.__name__ for command in commands]


def test_command_loader_deduplicates_aliased_classes(fake_root_package: str) -> None:
    commands = CommandLoader("widgets", NullLogRepository(), root_package=fake_root_package).get_all()

    # FooCommand and AliasedFooCommand are the same class object -- only one
    # entry should ever be returned, regardless of how many names bind it.
    assert len(commands) == 1


def test_command_loader_root_package_default_is_unaffected() -> None:
    # The default (omitted) root_package keeps discovering ontobdc's own
    # commands exactly as before -- this is the backward-compatibility
    # guarantee the root_package parameter must not break.
    commands = CommandLoader("cli", NullLogRepository()).get_all()
    assert any(command.__name__ == "CliInitCommand" for command in commands)
