from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import InteractiveCommandResponse
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.storage.adapter.explorer import (
    StorageElementExplorerAdapter,
    StorageElementMarkdownAdapter,
)
from ontobdc.storage.plugin.command.element import StorageElementCommand
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy


class StorageExploreCommand(StorageElementCommand):
    """Explore storage elements in a standalone Textual Markdown viewer."""

    ACTIONS: ClassVar[Tuple[str, ...]] = ("--element", "--explore")
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="explore",
        logical_component="storage",
        description=(
            "Explore the selected container's elements in an interactive "
            "Markdown viewer."
        ),
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "description": (
                    "Select a registered container by ID or filesystem path."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "--explore "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": False,
                "description": "Target the selected container's elements.",
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "--explore "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--explore"],
                "valued": False,
                "description": (
                    "Open the selected container's elements in Textual."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "--explore "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": (
                    "Filter explored elements by an entity URI or "
                    "entity_identifier."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "--explore "
                    "--entity <entity-uri-or-identifier>"
                ),
            },
        ],
    )

    def __init__(
        self,
        request: CliCommandRequest,
        markdown_adapter: Optional[StorageElementMarkdownAdapter] = None,
        explorer_adapter: Optional[StorageElementExplorerAdapter] = None,
    ) -> None:
        super().__init__(request)
        self._markdown_adapter: StorageElementMarkdownAdapter = (
            markdown_adapter or StorageElementMarkdownAdapter()
        )
        self._explorer_adapter: StorageElementExplorerAdapter = (
            explorer_adapter or StorageElementExplorerAdapter()
        )

    def run(self) -> InteractiveCommandResponse:
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        element_rows: List[Dict[str, Any]] = self._filtered_element_rows(
            self._list_data_entity_instances(container_path=container_path)
        )
        self._explorer_adapter.open_lazy(
            element_rows,
            markdown_adapter=self._markdown_adapter,
        )
        return InteractiveCommandResponse(
            title="Storage Element Explorer",
            description=(
                f"Explored {len(element_rows)} obdc:DataEntity instance(s)."
            ),
            content={},
        )


class StorageElementExploreOneCommand(StorageElementCommand):
    """Open exactly one element in the single-document Textual viewer.

    ``storage --container <id> --element <element_id> --explore``. Reuses
    the same brand-styled :class:`StorageElementExplorerApp` as the
    all-elements explorer above, but scoped to a single selected element
    instead of every element in the container.

    The content shown is currently the same facade-projected field/value
    document :meth:`StorageElementMarkdownAdapter.build_one` already
    produces — an interim source pending the facade-declared "standalone
    view tiles" design (rendering the element via the same terminal Tile
    machinery used elsewhere, resolved through ``ComponentLoader``)
    discussed with the user but not yet built.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="element_explore_one",
        logical_component="storage",
        description=(
            "Explore one selected element in the single-document Textual "
            "viewer."
        ),
        arguments=[
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": (
                    "Select a registered container by ID or filesystem path."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "<element_id> --explore"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Select one element by its identifier.",
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "<element_id> --explore"
                ),
            },
            {
                "accepts": ["--explore"],
                "valued": False,
                "description": (
                    "Open the selected element in the single-document "
                    "Textual viewer."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> --element "
                    "<element_id> --explore"
                ),
            },
        ],
    )

    def __init__(
        self,
        request: CliCommandRequest,
        markdown_adapter: Optional[StorageElementMarkdownAdapter] = None,
        explorer_adapter: Optional[StorageElementExplorerAdapter] = None,
    ) -> None:
        super().__init__(request)
        self._markdown_adapter: StorageElementMarkdownAdapter = (
            markdown_adapter or StorageElementMarkdownAdapter()
        )
        self._explorer_adapter: StorageElementExplorerAdapter = (
            explorer_adapter or StorageElementExplorerAdapter()
        )
        self._element_id: str = ""

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 6
            and args[0] == "storage"
            and args[1] in {"--container-id", "--container"}
            and bool(str(args[2]).strip())
            and args[3] == "--element"
            and bool(str(args[4]).strip())
            and not str(args[4]).startswith("--")
            and args[5] == "--explore"
        )

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 5
            and command_args[0] in {"--container-id", "--container"}
            and command_args[2] == "--element"
            and command_args[4] == "--explore"
        ):
            return False

        container_selector: str = command_args[1].strip()
        element_id: str = command_args[3].strip()
        if not container_selector or not element_id or element_id.startswith("--"):
            return False

        self._request.context.set_parameter_value("container", container_selector)
        ContainerIdStrategy().execute(self._request.context)

        container_id: str = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        if not container_id or not container_path:
            raise CliCommandArgumentException(
                f"Invalid container selector: {container_selector}"
            )

        self._element_id = element_id
        return True

    def run(self) -> InteractiveCommandResponse:
        container_path: str = str(
            self._request.context.get_parameter_value("container_path") or ""
        ).strip()
        element_rows: List[Dict[str, Any]] = self._list_data_entity_instances(
            container_path=container_path
        )
        matched_element: Optional[Dict[str, Any]] = next(
            (
                row
                for row in element_rows
                if str(row.get("id") or "").strip() == self._element_id
            ),
            None,
        )
        if matched_element is None:
            raise CliCommandArgumentException(
                f"Element is not registered in this container: {self._element_id}"
            )

        content: str = self._markdown_adapter.build_standalone(matched_element)
        self._explorer_adapter.open(content)

        return InteractiveCommandResponse(
            title="Storage Element Explorer",
            description=f"Explored element {self._element_id}.",
            content={},
        )
