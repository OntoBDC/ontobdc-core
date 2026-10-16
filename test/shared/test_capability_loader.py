import importlib
import sys

import pytest

import ontobdc.cli  # Initialize the CLI before importing its shared loader.
from ontobdc.shared.adapter.loader import CapabilityLoader


@pytest.fixture
def loader(tmp_path, monkeypatch):
    package = tmp_path / 'isolated_capabilities'
    directory = package / 'domain' / 'plugin' / 'capability' / 'transformation'
    directory.mkdir(parents=True)
    for folder in [package, package / 'domain', package / 'domain/plugin',
                   package / 'domain/plugin/capability', directory]:
        (folder / '__init__.py').write_text('')
    monkeypatch.syspath_prepend(str(tmp_path))
    instance = CapabilityLoader(root_packages=('isolated_capabilities',))
    yield instance, directory
    for name in list(sys.modules):
        if name.startswith('isolated_capabilities'):
            del sys.modules[name]
    importlib.invalidate_caches()


def test_imports_only_requested_module(loader, capsys):
    instance, directory = loader
    capability_id = 'org.ontobdc.container.plugin.capability.transformation.target.container_cleaned'
    (directory / 'wanted.py').write_text(
        f'ID = {capability_id!r}\n'
        'from ontobdc.container.plugin.capability.transformation.container_cleaned '
        'import ContainerCleanedCapability\n'
    )
    (directory / 'unrelated.py').write_text(
        'import dependency_that_is_not_installed\n'
    )
    assert instance.get(capability_id).__name__ == 'ContainerCleanedCapability'
    assert not any(name.endswith('.unrelated') for name in sys.modules)
    assert capsys.readouterr().err == ''


def test_unknown_id_imports_nothing(loader, capsys):
    instance, directory = loader
    (directory / 'broken.py').write_text('raise RuntimeError("must not execute")\n')
    assert instance.get('unknown.capability') is None
    assert capsys.readouterr().err == ''


def test_requested_missing_dependency_is_not_hidden(loader):
    instance, directory = loader
    (directory / 'broken.py').write_text(
        'ID = "requested.capability"\nimport dependency_that_is_not_installed\n'
    )
    with pytest.raises(ModuleNotFoundError, match='dependency_that_is_not_installed'):
        instance.get('requested.capability')
