from pathlib import Path

import pytest

from ontobdc.comment.adapter.thread import CommentThread


def test_update_changes_text_and_author_and_keeps_the_rest(tmp_path: Path) -> None:
    thread: CommentThread = CommentThread(tmp_path, "entity-1")
    first = thread.add("one", "Ana")
    reply = thread.add("two", "Bia", reply_of=first["global_id"])

    changed = thread.update(first["global_id"], text="uno", author="Cris")

    assert (changed["text"], changed["author"]) == ("uno", "Cris")
    comments = {comment["global_id"]: comment for comment in thread.comments()}
    assert comments[first["global_id"]]["created_at"] == first["created_at"]
    assert comments[reply["global_id"]]["reply_of"] == first["global_id"]
    assert comments[reply["global_id"]]["text"] == "two"


def test_update_with_only_the_author_leaves_the_text(tmp_path: Path) -> None:
    thread: CommentThread = CommentThread(tmp_path, "entity-1")
    comment = thread.add("one", "")

    changed = thread.update(comment["global_id"], author="Ana")

    assert (changed["text"], changed["author"]) == ("one", "Ana")


def test_update_fails_for_an_unknown_comment_and_for_nothing_to_change(tmp_path: Path) -> None:
    thread: CommentThread = CommentThread(tmp_path, "entity-1")
    comment = thread.add("one", "Ana")

    with pytest.raises(LookupError):
        thread.update("nope", text="x")
    with pytest.raises(ValueError):
        thread.update(comment["global_id"])
