
import importlib
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
)

from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.shared.adapter.terminal_text import TerminalTextMetrics
from ontobdc.cli.domain.model.command import CliCommandMetadata


class TerminalTreeAdapter:
    """Render an arbitrary nested dict or path list as a generic ASCII tree.

    Pure rendering concern — no command discovery, no usage parsing, no
    filesystem access. Any adapter that needs a classic ``├──`` / ``└──``
    terminal tree can instantiate this class with its own tokens.
    """

    _FLAG_PREFIX: ClassVar[str] = "-"

    def __init__(
        self,
        root_label: str,
        flag_styler: Callable[[str], str],
        piece_separator: str,
        connector_branch: str,
        connector_leaf: str,
        prefix_branch: str,
        prefix_leaf: str,
    ) -> None:
        self._root_label: str = root_label
        self._flag_styler: Callable[[str], str] = flag_styler
        self._piece_separator: str = piece_separator
        self._connector_branch: str = connector_branch
        self._connector_leaf: str = connector_leaf
        self._prefix_branch: str = prefix_branch
        self._prefix_leaf: str = prefix_leaf

    @staticmethod
    def default_flag_styler(token: str) -> str:
        return token

    @classmethod
    def paths_to_trie(
        cls,
        paths: List[List[str]],
    ) -> Dict[str, Dict[str, Any]]:
        """Build a nested trie dict from a list of tokenised paths.

        The **text of every trie node** comes directly from each ``token`` in
        the input path list: for ``["container", "create"]`` the produced
        trie will have the children keys ``"container"`` → ``"create"``
        (via ``dict.setdefault(token, {})``).  The caller of
        :meth:`render_trie` therefore controls all non-root node labels by
        choosing what tokens to put into each path before calling this
        builder.
        """
        trie: Dict[str, Dict[str, Any]] = {}
        for path in paths:
            node: Dict[str, Dict[str, Any]] = trie
            for token in path:
                node = node.setdefault(token, {})
        return trie

    def render_paths(self, paths: List[List[str]]) -> str:
        return self.render_trie(self.paths_to_trie(paths))

    def render_trie(self, tree: Dict[str, Dict[str, Any]]) -> str:
        """Render a nested trie dict as a multi-line ASCII tree.

        Node text is placed in **three distinct places** depending on the
        nesting level:

        1. **Root node (first line)**.
           Populated from ``self._root_label`` (mandatory constructor
           argument, no default — the caller is forced to declare what the
           tree represents).  Written once as ``lines = [self._root_label]``
           before recursing into children.

        2. **Leaf and internal nodes (every remaining line)**.
           The inner ``append_nodes`` recursion walks ``tree.keys()``; each
           child's label is the trie **dictionary key itself** (for example
           ``"container"`` or ``"CliContainerCreateCommand"``), styled
           through ``style_token(key)``.  ``style_token`` applies the
           configured ``flag_styler`` to plain tokens and, for compound
           labels that contain ``self._piece_separator`` (e.g.
           ``"-f|--flag"``), splits the value, styles each piece
           independently and rejoins them with the separator.

        Because the render function never invent labels — it only emits
        ``_root_label`` plus the keys of whatever dict was passed in — the
        builder function (:meth:`paths_to_trie`,
        :meth:`CommandTreeAdapter._to_simple_trie` or a caller-supplied
        dict) has full control over every visible string in the final
        output.
        """
        lines: List[str] = [self._root_label]

        def style_token(token: str) -> str:
            if self._piece_separator not in token:
                return self._flag_styler(token)
            styled_pieces: List[str] = []
            for piece in token.split(self._piece_separator):
                styled_pieces.append(self._flag_styler(piece))
            return self._piece_separator.join(styled_pieces)

        def append_nodes(
            node: Dict[str, Dict[str, Any]], prefix: str
        ) -> None:
            keys: List[str] = list(node.keys())
            for index, key in enumerate(keys):
                is_last: bool = index == len(keys) - 1
                connector: str = (
                    self._connector_leaf if is_last else self._connector_branch
                )
                styled_key: str = style_token(key)
                lines.append(f"{prefix}{connector}{styled_key}")
                child_prefix: str = prefix + (
                    self._prefix_leaf if is_last else self._prefix_branch
                )
                meta: Dict[str, Any] = node[key]
                if not isinstance(meta, dict):
                    raise TypeError(
                        "Trie child value must be a dict mapping; got "
                        f"{type(meta).__name__}"
                    )
                if "__description__" in meta and meta["__description__"]:
                    raw_description: str = meta["__description__"]
                    terminal_columns: int = shutil.get_terminal_size().columns
                    prefix_visible_width: int = TerminalTextMetrics.visible_width(
                        child_prefix
                    )
                    box_frame_and_right_gap: int = 5
                    wrap_width: int = (
                        terminal_columns
                        - box_frame_and_right_gap
                        - prefix_visible_width
                    )
                    if wrap_width < 1:
                        raise ValueError(
                            "Computed description wrap width is less than 1 "
                            f"(columns={terminal_columns}, prefix_width="
                            f"{prefix_visible_width}, gap={box_frame_and_right_gap})."
                        )
                    collapsed: str = " ".join(raw_description.split())
                    all_lines: List[str] = []
                    cursor: int = 0
                    total: int = len(collapsed)
                    while cursor < total:
                        take: int = 1
                        while (
                            cursor + take <= total
                            and TerminalTextMetrics.visible_width(
                                collapsed[cursor : cursor + take]
                            )
                            <= wrap_width
                        ):
                            take += 1
                        slice_end: int = cursor + take - 1
                        chunk: str = collapsed[cursor:slice_end]
                        if (
                            slice_end < total
                            and chunk.rfind(" ") > 0
                        ):
                            space_at: int = chunk.rfind(" ")
                            chunk = chunk[:space_at]
                            slice_end = cursor + space_at + 1
                        if chunk.strip():
                            all_lines.append(chunk.strip())
                        cursor = slice_end
                        while cursor < total and collapsed[cursor] == " ":
                            cursor += 1
                    for wrapped_line in all_lines:
                        lines.append(
                            f"{child_prefix}"
                            f"{TerminalColor.GRAY}"
                            f"{wrapped_line}"
                            f"{TerminalColor.RESET}"
                        )
                child: Dict[str, Dict[str, Any]] = {
                    child_key: child_value
                    for child_key, child_value in meta.items()
                    if not child_key.startswith("__")
                }
                if child:
                    append_nodes(child, child_prefix)

        append_nodes(tree, "")
        return "\n".join(lines)


class CommandTreeAdapter:
    """Discover registered CLI commands and expose structured descriptions.

    CommandTreeAdapter owns one single responsibility: walk the plugin
    directories and collect ``CliCommandPort`` classes grouped by logical
    component. It does **not** own ASCII rendering; that is delegated to
    :class:`TerminalTreeAdapter` so rendering concerns stay reusable.
    """

    NO_EXCLUDED_COMMAND_IDS: ClassVar[Tuple[str, ...]] = ()
    NO_EXECUTABLE_ALIASES: ClassVar[Tuple[str, ...]] = ()
    NO_COMMAND_CLASSES: ClassVar[Tuple[Tuple[str, Type[CliCommandPort]], ...]] = ()

    def __init__(
        self,
        logger: LogRepositoryPort,
        root_package: str,
        executable: str,
        excluded_command_ids: Tuple[str, ...] = NO_EXCLUDED_COMMAND_IDS,
        command_classes: Iterable[Tuple[str, Type[CliCommandPort]]] = NO_COMMAND_CLASSES,
        executable_aliases: Tuple[str, ...] = NO_EXECUTABLE_ALIASES,
    ) -> None:
        self._executable: str = executable
        self._root_package: str = root_package
        self._excluded_ids: Set[str] = set(excluded_command_ids)
        self._executable_aliases: Tuple[str, ...] = tuple(executable_aliases)
        explicit_pairs: List[Tuple[str, Type[CliCommandPort]]] = list(command_classes)
        self._root_scan_dir: str = CommandTreeAdapter.get_package_root_dir(
            root_package=root_package,
            executable=executable,
        )
        self._logger: LogRepositoryPort = logger
        self._explicit_commands: List[Tuple[str, Type[CliCommandPort]]] = explicit_pairs
        self._tree_renderer: TerminalTreeAdapter = TerminalTreeAdapter(
            root_label=executable,
            flag_styler=TerminalTreeAdapter.default_flag_styler,
            piece_separator=" | ",
            connector_branch="├── ",
            connector_leaf="└── ",
            prefix_branch="│   ",
            prefix_leaf="    ",
        )

    @staticmethod
    def get_package_root_dir(
        root_package: str,
        executable: Optional[str] = None,
    ) -> str:
        """
        Resolve the absolute filesystem directory of ``root_package``.

        Works for **any** installed package, not just the ontobdc runtime.
        The strategy mirrors what :meth:`ConfigDataAdapter.get_script_dir`
        already does for ``ontobdc``, but parameterised on the caller's
        ``root_package`` so downstream projects such as InfoBIM can also
        walk their plugin/command trees without the caller having to
        ``chdir`` into the repository source root.

        Priority order:

        1. If the package is importable and exposes ``__path__``, iterate
           every entry and return the first one that contains the canonical
           subdirectories a package of this kind ships (``cli`` + ``shared``
           for the ontobdc executable, or ``cli`` for anything else — that
           is the minimum the CLI tree scanner relies on).
        2. Otherwise fall back to ``pip show <package-name> | grep Location``
           and append the package name.
        3. Last resort: the directory that contains the *caller* module of
           this adapter (keeps behaviour unchanged for editable installs
           whose subprocess step is unavailable or broken).
        """
        canonical_dirs: Tuple[str, ...]
        if executable == "ontobdc":
            canonical_dirs = ("cli", "shared")
        else:
            canonical_dirs = ("cli",)

        try:
            imported = importlib.import_module(root_package)
            if hasattr(imported, "__path__"):
                for package_path in list(imported.__path__):
                    candidate: Path = Path(package_path).expanduser().resolve()
                    if all(
                        (candidate / directory_name).is_dir()
                        for directory_name in canonical_dirs
                    ):
                        return str(candidate)

                fallback_path = list(imported.__path__)[0]
                return str(Path(fallback_path).expanduser().resolve())
        except Exception:
            pass

        try:
            location: str = (
                subprocess.check_output(["pip", "show", root_package])
                .decode("utf-8")
                .split("Location:")
            )[1].strip().splitlines()[0].strip()
            if location:
                return os.path.join(location, root_package)
        except Exception:
            pass

        script_dir: str = os.path.dirname(os.path.abspath(__file__))
        module_root: str = os.path.abspath(os.path.join(script_dir, "..", ".."))
        return module_root

    def describe(self) -> Dict[str, Dict[str, Any]]:
        discovered: Dict[str, List[Type[CliCommandPort]]] = self._discover()
        return self._to_description(discovered)

    def discover_command_paths(self) -> List[List[str]]:
        discovered: Dict[str, List[Type[CliCommandPort]]] = self._discover()
        paths: List[List[str]] = []
        for module, commands in discovered.items():
            for command_class in commands:
                metadata: CliCommandMetadata = command_class.METADATA
                command_forms: List[str] = []
                command_forms.append(metadata.id)
                arguments: List[Dict[str, Any]] = list(metadata.arguments)
                for argument_definition in arguments:
                    accepts: List[str] = list(argument_definition["accepts"])
                    valued_raw: Any = argument_definition.get("valued", False)
                    valued: bool = bool(valued_raw)
                    flag_joined: str = " | ".join(accepts)
                    command_forms.append(flag_joined)
                paths.append(command_forms)
        for alias in self._executable_aliases:
            alias_prefix: List[str] = [alias]
            sibling_paths: List[List[str]] = []
            for base in paths:
                without_executable: List[str] = list(base)
                sibling_paths.append(alias_prefix + without_executable)
            paths.extend(sibling_paths)
        return paths

    def render(self) -> str:
        discovered: Dict[str, List[Type[CliCommandPort]]] = self._discover()
        trie: Dict[str, Dict[str, Any]] = self._to_simple_trie(self._to_description(discovered))

        return self._tree_renderer.render_trie(trie)

    def _discover(self) -> Dict[str, List[Type[CliCommandPort]]]:
        discovered: Dict[str, List[Type[CliCommandPort]]] = {}
        if self._explicit_commands:
            for component, command_class in self._explicit_commands:
                metadata: CliCommandMetadata = command_class.METADATA
                if metadata.id in self._excluded_ids:
                    continue
                component_list: List[Type[CliCommandPort]] = discovered.setdefault(component, [])
                component_list.append(command_class)
            return discovered
        for module in self._scan_module():
            commands: List[Type[CliCommandPort]] = CommandLoader(
                module, self._logger, self._root_package,
            ).get_all()
            filtered: List[Type[CliCommandPort]] = []
            for command_class in commands:
                command_metadata: CliCommandMetadata = command_class.METADATA
                if command_metadata.id in self._excluded_ids:
                    continue
                filtered.append(command_class)
            if filtered:
                discovered[module] = filtered
        return discovered

    def _scan_module(self) -> List[str]:
        discovered: List[str] = []
        base_dir: str = self._root_scan_dir

        for entry in sorted(os.listdir(base_dir)):
            if entry.startswith(".") or entry.startswith("_") or entry == "__pycache__":
                continue

            entry_path: str = os.path.join(base_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            resource_dir: str = os.path.join(entry_path, "plugin")
            if not os.path.isdir(resource_dir):
                continue

            resource_dir = os.path.join(resource_dir, "command")
            if not os.path.isdir(resource_dir):
                continue
            directory_entries: List[str] = sorted(os.listdir(resource_dir))
            only_proxy_placeholder: bool = (
                len(directory_entries) == 1 and directory_entries[0] == "proxy.py"
            )
            if only_proxy_placeholder:
                continue
            discovered.append(entry)

        return discovered

    @staticmethod
    def _to_description(
        discovered: Dict[str, List[Type[CliCommandPort]]],
    ) -> Dict[str, Dict[str, Any]]:
        tree: Dict[str, Dict[str, Any]] = {}
        for module, commands in discovered.items():
            tree[module] = {}
            for command_class in commands:
                key: str = command_class.__name__
                metadata: CliCommandMetadata = command_class.METADATA
                description_text: str = str(metadata.description)
                arguments_raw: List[Dict[str, Any]] = list(metadata.arguments)
                arguments_out: List[Dict[str, Any]] = []
                for argument_definition in arguments_raw:
                    accepts_value: Any = argument_definition["accepts"]
                    accepts: List[str] = list(accepts_value)
                    valued_raw: Any = argument_definition.get("valued", False)
                    valued: bool = bool(valued_raw)
                    optional_raw: Any = argument_definition.get("optional", False)
                    optional: bool = bool(optional_raw)
                    description_raw: Any = argument_definition["description"]
                    arguments_out.append({
                        "flag": "|".join(accepts),
                        "valued": valued,
                        "optional": optional,
                        "description": str(description_raw),
                    })
                tree[module][key] = {
                    "name": key,
                    "description": description_text,
                    "arguments": arguments_out,
                }
        return tree

    @staticmethod
    def _to_simple_trie(
        description: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Build the two-level display trie used by the tree surface.

        The ``description`` mapping is the output of
        :meth:`_to_description` and contains, for each logical module and
        command class, the user-facing labels of the command and its
        arguments.  The trie is shaped as follows:

        * **First level** — the logical module / component name
          (``"cli"``, ``"container"``, ``"context"`` …), taken verbatim from
          the outer keys of ``description`` (one entry per plugin folder).
        * **Second level** — the **inline argument usage** only.  The
          command class name is deliberately omitted from the tree label;
          readers identify commands by their usage shape.  Every declared
          argument is rendered with its joined accept string, suffixed by
          ``<value>`` when ``valued`` is true.  Decorators accumulate on a
          best-effort basis:

          - multi-form arguments (``len(accepts) > 1``) are wrapped in
            ``{a|b|c}``;
          - optional arguments (explicit ``optional: True`` on the argument
            definition) are additionally wrapped in ``[ … ]`` so a
            multi-form optional valued argument ends up as
            ``[{a|b|c} <value>]`` after both wrappers are applied in
            order.  ``optional: False`` or an absent ``optional`` key are
            treated the same way: the argument is mandatory and its usage
            line carries no ``[]`` wrapper.

          A command that declares no arguments at all (the bare
          executable) is labelled ``(no arguments)`` instead of an empty
          line.

          The corresponding command description is carried in the child
          dict under the reserved ``"__description__"`` key and is emitted
          right below the usage line in
          :meth:`TerminalTreeAdapter.render_trie` using the configured
          grey style.
        """
        trie: Dict[str, Dict[str, Any]] = {}
        for module, commands in description.items():
            module_node: Dict[str, Any] = trie.setdefault(module, {})
            for _command_key, command_info in commands.items():
                argument_parts: List[str] = []
                for arg in command_info["arguments"]:
                    flag: str = arg["flag"]
                    if arg["valued"]:
                        flag = f"{flag} <value>"
                    is_multi_form: bool = "|" in arg["flag"]
                    is_optional: bool = arg["optional"]
                    if is_multi_form:
                        flag = f"{{{flag}}}"
                    if is_optional:
                        flag = f"[{flag}]"
                    argument_parts.append(flag)
                command_label: str = " ".join(argument_parts) or "(no arguments)"
                command_node: Dict[str, Any] = {"__description__": command_info["description"]}
                module_node[command_label] = command_node
        return trie
