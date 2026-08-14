from pathlib import Path
from unittest.mock import patch

import pytest

from ontobdc.shared.adapter.filesystem import remove_directory_tree


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

    def flaky_rmtree(path):
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

    def always_locked(path):
        raise PermissionError(5, "Access is denied")

    with patch("ontobdc.shared.adapter.filesystem.shutil.rmtree", side_effect=always_locked):
        with patch("ontobdc.shared.adapter.filesystem.time.sleep"):
            with pytest.raises(OSError, match="still in use after 5 attempts"):
                remove_directory_tree(target, attempts=5)
