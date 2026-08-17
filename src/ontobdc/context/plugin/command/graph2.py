from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, GraphCommandResponse
from ontobdc.context.adapter.graph import ContextGraphAdapter
from ontobdc.context.plugin.check.has_valid_context.check import main as check_has_valid_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_has_valid_context
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContextGraph2Command(CliCommandPort):
    """Render context.ttl with netext's Sugiyama graph layout."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="graph2",
        logical_component="context",
        description="Visualize context.ttl with the netext Sugiyama layout.",
        arguments=[
            {
                "accepts": ["--graph2"],
                "valued": False,
                "description": "Visualize the persisted context graph with netext.",
                "usage": "ontobdc context --graph2 [vertical]",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._graph_adapter: ContextGraphAdapter = ContextGraphAdapter()

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args in (
            ["context", "--graph2"],
            ["context", "--graph2", "vertical"],
        )

    def check(self) -> bool:
        if self._request.command_args not in (
            ["--graph2"],
            ["--graph2", "vertical"],
        ):
            return False

        root_path: str = str(self._request.context.root_path)
        if check_has_valid_context(root_path=root_path) != 0:
            hotfix_has_valid_context(root_path=root_path)
            self._request.context.reload()

        return check_has_valid_context(root_path=root_path) == 0

    def run(self) -> GraphCommandResponse:
        try:
            root_path: Path = Path(str(self._request.context.root_path)).expanduser().resolve()
            context_file_path: Path = StorageBootstrap.get_context_file_path(root_path=root_path)
            graph_data: Dict[str, Any] = self._graph_adapter.load(context_file_path)
            graph_data["layout"] = "layered"
            graph_data["orientation"] = (
                "vertical"
                if self._request.command_args == ["--graph2", "vertical"]
                else "layered"
            )

            return GraphCommandResponse(
                title="Context Graph 2",
                description=str(context_file_path),
                content=graph_data,
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Context Graph 2",
                description="Failed to visualize the persisted execution context.",
                content={"error": str(error)},
            )
