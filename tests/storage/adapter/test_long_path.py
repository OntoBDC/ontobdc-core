from pathlib import Path, PureWindowsPath
from unittest.mock import patch

import pytest

from ontobdc.storage.adapter.bootstrap import to_extended_length_path
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer


def test_to_extended_length_path_is_noop_on_posix():
    with patch("ontobdc.storage.adapter.bootstrap.os.name", "posix"):
        path = Path("/some/very/long/path.txt")
        assert to_extended_length_path(path) is path


def test_to_extended_length_path_prefixes_drive_path_on_windows():
    with patch("ontobdc.storage.adapter.bootstrap.os.name", "nt"):
        with patch("ontobdc.storage.adapter.bootstrap.Path", PureWindowsPath):
            result = to_extended_length_path(
                PureWindowsPath(r"C:\Users\test\long\folder\file.txt")
            )
    assert str(result) == r"\\?\C:\Users\test\long\folder\file.txt"


def test_to_extended_length_path_prefixes_unc_path_on_windows():
    with patch("ontobdc.storage.adapter.bootstrap.os.name", "nt"):
        with patch("ontobdc.storage.adapter.bootstrap.Path", PureWindowsPath):
            result = to_extended_length_path(
                PureWindowsPath(r"\\server\share\file.txt")
            )
    assert str(result) == r"\\?\UNC\server\share\file.txt"


def test_to_extended_length_path_is_idempotent_on_windows():
    with patch("ontobdc.storage.adapter.bootstrap.os.name", "nt"):
        with patch("ontobdc.storage.adapter.bootstrap.Path", PureWindowsPath):
            already_prefixed = PureWindowsPath(r"\\?\C:\already\prefixed.txt")
            result = to_extended_length_path(already_prefixed)
    assert result is already_prefixed


def test_build_local_descriptor_stats_through_extended_length_path(tmp_path):
    # Reproduces the reported WinError 3: a real file whose stat() call
    # must go through to_extended_length_path() instead of the raw path,
    # so a >260-character absolute path doesn't crash on Windows.
    long_directory = tmp_path / ("nested_" * 20)
    long_directory.mkdir(parents=True)
    target_file = long_directory / "document.doc"
    target_file.write_bytes(b"content")
    relative_path = target_file.relative_to(tmp_path).as_posix()

    with patch(
        "ontobdc.storage.adapter.manifest.to_extended_length_path",
        wraps=lambda path: path,
    ) as extended_path_spy:
        descriptor = ContainerDataPackageSynchronizer()._build_local_descriptor(
            relative_path=relative_path,
            container_path=tmp_path,
            datapackage_path=tmp_path / ".__ontobdc__" / "datapackage.json",
            existing_descriptor=None,
        )

    extended_path_spy.assert_called_once_with(target_file)
    assert descriptor["bytes"] == len(b"content")
