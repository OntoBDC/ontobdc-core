import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ontobdc.shared.adapter.filesystem import (
    _clear_readonly_and_retry,
    remove_directory_tree,
    remove_file,
)


# -- remove_directory_tree ----------------------------------------------


def test_removes_directory_on_first_try(tmp_path):
    target = tmp_path / "state"
    target.mkdir()
    (target / "file.txt").write_text("content")

    remove_directory_tree(target)

    assert not target.exists()


def test_retries_and_succeeds_after_transient_permission_error(tmp_path):
    target = tmp_path / "state"
    target.mkdir()

    call_count = {"value": 0}
    real_rmtree = __import__("shutil").rmtree

    def flaky_rmtree(path, onexc=None):
        call_count["value"] += 1
        if call_count["value"] < 3:
            raise PermissionError(5, "Access is denied")
        real_rmtree(path)

    with patch("ontobdc.shared.adapter.filesystem.shutil.rmtree", side_effect=flaky_rmtree):
        with patch("ontobdc.shared.adapter.filesystem.time.sleep"):
            remove_directory_tree(target)

    assert call_count["value"] == 3
    assert not target.exists()


def test_raises_after_exhausting_attempts(tmp_path):
    target = tmp_path / "state"
    target.mkdir()

    def always_locked(path, onexc=None):
        raise PermissionError(5, "Access is denied")

    with patch("ontobdc.shared.adapter.filesystem.shutil.rmtree", side_effect=always_locked):
        with patch("ontobdc.shared.adapter.filesystem.time.sleep"):
            with pytest.raises(OSError, match="still in use after 5 attempts"):
                remove_directory_tree(target, attempts=5)


def test_clear_readonly_and_retry_chmods_and_calls_function(tmp_path):
    target = tmp_path / "readonly.txt"
    target.write_text("content")
    target.chmod(stat.S_IREAD)

    function = MagicMock()

    _clear_readonly_and_retry(function, target, None)

    assert target.stat().st_mode & stat.S_IWRITE
    function.assert_called_once_with(target)


# -- remove_file -----------------------------------------------------------


def test_remove_file_removes_on_first_try(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("content")

    remove_file(target)

    assert not target.exists()


def test_remove_file_missing_file_is_noop(tmp_path):
    target = tmp_path / "does-not-exist.txt"

    remove_file(target)


def test_remove_file_clears_readonly_on_permission_error(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("content")
    target.chmod(stat.S_IREAD)

    remove_file(target)

    assert not target.exists()


def test_remove_file_raises_after_exhausting_attempts(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("content")

    with patch(
        "ontobdc.shared.adapter.filesystem.Path.unlink",
        side_effect=PermissionError(5, "Access is denied"),
    ):
        with patch("ontobdc.shared.adapter.filesystem.os.chmod"):
            with patch("ontobdc.shared.adapter.filesystem.time.sleep"):
                with pytest.raises(OSError, match="still in use after 5 attempts"):
                    remove_file(target, attempts=5)
