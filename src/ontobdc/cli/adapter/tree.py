
import re
from typing import (
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Pattern,
    Tuple,
    Type,
)

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.shared.adapter.terminal_color import GRAY, RESET
from ontobdc.shared.facade.adapter.logger import NullLogRepository


class CommandTreeAdapter:
    """Discover registered CLI commands and render them as an ASCII tree.

    Responsibility: crawl every plugin-registered command across logical
    components, extract the declarative ``usage`` / ``accepts`` metadata,
    deduplicate the resulting token paths, and render the classic
    ``├──`` / ``└──`` tree used by the CLI help response.

    This adapter intentionally owns zero runtime-execution concerns: it only
    reads ``CliCommandMetadata`` and produces the printable string consumed
    by :class:`ontobdc.cli.plugin.command.base.CliBaseCommand`.
    """

    _PLACEHOLDER_CHARS: ClassVar[Pattern[str]] = re.compile(
        r'"[^"]*"|\[[^\]]*\]|<[^>]*>'
    )

    _PRESET_TOKEN_BLOCKLIST: ClassVar[FrozenSet[str]] = frozenset({
        "html", "json", "rich", "standard",
        "pt-br", "en", "en-us",
    })

    def __init__(
        self,
        logger: Optional[LogRepositoryPort] = None,
        root_package: str = "ontobdc",
        executable: str = "ontobdc",
        excluded_command_ids: Tuple[str, ...] = ("base",),
    ) -> None:
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._root_package: str = root_package
        self._executable: str = executable
        self._excluded_command_ids: FrozenSet[str] = frozenset(
            excluded_command_ids
        )

    def render(self) -> str:
        paths: List[List[str]] = self.discover_command_paths()
        tree: Dict[str, Dict[str, Any]] = self._paths_to_trie(paths)
        return self._render_trie(tree)

    def discover_command_paths(self) -> List[List[str]]:
        paths: List[List[str]] = []
        command_classes: List[Tuple[str, Type[CliCommandPort]]] = (
            self._discover_command_classes()
        )
        component: str
        command_class: Type[CliCommandPort]
        for component, command_class in command_classes:
            metadata = command_class.METADATA
            argument_definitions: List[Dict[str, Any]] = metadata.arguments or []

            base_tokens: List[str]
            if component == "cli":
                base_tokens = []
            else:
                base_tokens = [component]

            found_any_usage: bool = False
            argument_definition: Dict[str, Any]
            for argument_definition in argument_definitions:
                usage: Optional[str] = argument_definition.get("usage")
                accepted_arguments: List[str] = list(
                    argument_definition.get("accepts", [])
                )
                accepts_label: str
                if accepted_arguments:
                    accepts_label = " | ".join(
                        self._grey_token(f) if f.startswith("-") else f
                        for f in accepted_arguments
                    )
                if usage:
                    alternatives: List[str] = [
                        piece.strip()
                        for piece in str(usage).split("|")
                        if piece.strip()
                    ]
                    if not alternatives:
                        alternatives = [str(usage)]
                    alt: str
                    for alt in alternatives:
                        normalized: str = alt
                        if component == "dev":
                            normalized = normalized.replace(
                                f"{self._executable} dev",
                                self._executable,
                            )
                        path: List[str] = self._usage_to_path(
                            normalized, component
                        )
                        if not path:
                            continue
                        if (
                            accepted_arguments
                            and len(path) >= 1
                            and path[-1] in accepted_arguments
                        ):
                            if len(path) == 1:
                                full: List[str] = (
                                    list(base_tokens) + [accepts_label]
                                )
                            else:
                                full = (
                                    list(base_tokens)
                                    + path[:-1]
                                    + [accepts_label]
                                )
                        else:
                            full = list(base_tokens) + path
                        if full not in paths:
                            paths.append(full)
                        found_any_usage = True
                    continue

                accepted: str
                for accepted in accepted_arguments:
                    if not accepted:
                        continue
                    if accepts_label:
                        token_path: List[str] = (
                            list(base_tokens) + [accepts_label]
                        )
                    else:
                        token_path = list(base_tokens) + [accepted]
                    if token_path not in paths:
                        paths.append(token_path)

            if not found_any_usage and not argument_definitions:
                token_path = list(base_tokens)
                if token_path and token_path not in paths:
                    paths.append(token_path)

        return sorted(paths, key=lambda item: tuple(item))

    def _usage_to_path(self, usage: str, component: str) -> List[str]:
        raw: str = str(usage).strip()
        if not raw:
            return []
        stripped: str = self._PLACEHOLDER_CHARS.sub(" ", raw)

        tokens: List[str] = stripped.split()
        if not tokens:
            return []

        if tokens[0] == self._executable:
            tokens = tokens[1:]
            if tokens and tokens[0] == component:
                tokens = tokens[1:]
            if component == "dev" and tokens and tokens[0] == "dev":
                tokens = tokens[1:]

        if component != "cli":
            if tokens and tokens[0] == component:
                tokens = tokens[1:]

        cleaned: List[str] = []
        token: str
        for token in tokens:
            if not token:
                continue
            if any(ch in token for ch in "<>[]\"'|"):
                continue
            if token == self._executable:
                continue
            if token.lower() in self._PRESET_TOKEN_BLOCKLIST:
                continue
            cleaned.append(token)
        return cleaned

    @classmethod
    def _grey_token(cls, token: str) -> str:
        if not token:
            return token
        if token.startswith("-"):
            return f"{GRAY}{token}{RESET}"
        return token

    @classmethod
    def _paths_to_trie(
        cls, paths: List[List[str]]
    ) -> Dict[str, Dict[str, Any]]:
        tree: Dict[str, Dict[str, Any]] = {}
        for path in paths:
            node: Dict[str, Dict[str, Any]] = tree
            token: str
            for token in path:
                node = node.setdefault(token, {})
        return tree

    def _render_trie(self, tree: Dict[str, Dict[str, Any]]) -> str:
        lines: List[str] = [self._executable]

        def render_token_plain(token: str) -> str:
            if not token:
                return token
            if " | " not in token:
                if token.startswith("-"):
                    return f"{GRAY}{token}{RESET}"
                return token
            pieces: List[str] = []
            piece: str
            for piece in token.split(" | "):
                if piece.startswith("-"):
                    pieces.append(f"{GRAY}{piece}{RESET}")
                else:
                    pieces.append(piece)
            return " | ".join(pieces)

        def append_nodes(
            node: Dict[str, Dict[str, Any]], prefix: str
        ) -> None:
            keys: List[str] = list(node.keys())
            index: int
            key: str
            for index, key in enumerate(keys):
                is_last: bool = index == len(keys) - 1
                connector: str = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{render_token_plain(key)}")
                child_prefix: str = prefix + (
                    "    " if is_last else "│   "
                )
                if node[key]:
                    append_nodes(node[key], child_prefix)

        append_nodes(tree, "")
        return "\n".join(lines)

    def _discover_logical_components(self) -> List[str]:
        dummy_loader: CommandLoader = CommandLoader(
            "",
            self._logger,
            root_package=self._root_package,
        )
        try:
            plugin_packages: List[str] = dummy_loader._list_plugin_folder(
                "command",
                root_package=self._root_package,
            )
        except Exception:
            plugin_packages = []
        components: List[str] = []
        seen: set = set()
        for pkg in plugin_packages:
            segments: List[str] = pkg.split(".")
            if len(segments) < 2:
                continue
            candidate: str = segments[1]
            if candidate in seen:
                continue
            seen.add(candidate)
            components.append(candidate)
        return sorted(components)

    def _discover_command_classes(
        self,
    ) -> List[Tuple[str, Type[CliCommandPort]]]:
        components: List[str] = self._discover_logical_components()
        result: List[Tuple[str, Type[CliCommandPort]]] = []
        component: str
        for component in components:
            try:
                loader: CommandLoader = CommandLoader(
                    component,
                    self._logger,
                    root_package=self._root_package,
                )
            except Exception:
                continue
            cmd_class: Type[CliCommandPort]
            for cmd_class in loader.get_all():
                if not isinstance(cmd_class, type):
                    continue
                if cmd_class.METADATA.id in self._excluded_command_ids:
                    continue
                result.append((component, cmd_class))
        return result
