from pathlib import Path
from typing import Iterator

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner


@pytest.fixture
def cli_runner(tmp_path: Path) -> Iterator[OntobdcCliProcessRunner]:
    """
    An `ontobdc` process runner scoped to an isolated, empty project root so
    real CLI invocations never touch the developer's `.__ontobdc__/context.ttl`.
    """
    yield OntobdcCliProcessRunner(isolated_project_root=tmp_path)
