from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    GroupedGraphCommandResponse,
)
from ontobdc.context.adapter.graph import ContextGraphAdapter
from ontobdc.context.plugin.check.has_valid_context.check import main as check_has_valid_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_has_valid_context
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContextGraphCommand(CliCommandPort):
    """Render the persisted context Turtle file grouped by subject.

    `context.ttl` is structurally a single-subject graph (one
    `:CurrentContext` individual with a handful of properties), so this
    groups by subject rather than drawing a node-link diagram — one heading
    per subject, its properties listed underneath, the same shape Turtle's
    own subject grouping produces. See `--graph2` for an actual node-link
    rendering (netext), useful for comparing layouts on richer graphs.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="graph",
        logical_component="context",
        description="Visualize context.ttl grouped by subject.",
        arguments=[
            {
                "accepts": ["--graph"],
                "valued": False,
                "description": "Visualize the persisted context Turtle graph, grouped by subject.",
                "usage": "ontobdc context --graph",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._graph_adapter: ContextGraphAdapter = ContextGraphAdapter()

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args == ["context", "--graph"]

    def check(self) -> bool:
        if self._request.command_args != ["--graph"]:
            return False

        root_path: str = str(self._request.context.root_path)
        if check_has_valid_context(root_path=root_path) != 0:
            hotfix_has_valid_context(root_path=root_path)
            self._request.context.reload()

        return check_has_valid_context(root_path=root_path) == 0

    def run(self) -> CommandResponse:
        try:
            root_path: Path = Path(str(self._request.context.root_path)).expanduser().resolve()
            context_file_path: Path = StorageBootstrap.get_context_file_path(root_path=root_path)
            graph_data: Dict[str, Any] = self._graph_adapter.load(context_file_path)

            return GroupedGraphCommandResponse(
                title="Context Graph",
                description=str(context_file_path),
                content=graph_data,
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Context Graph",
                description="Failed to visualize the persisted execution context.",
                content={"error": str(error)},
            )
