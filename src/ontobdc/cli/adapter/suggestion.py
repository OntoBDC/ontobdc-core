from typing import ClassVar, List, Optional, Tuple
from difflib import SequenceMatcher

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.cli.domain.port.suggestion import CommandSuggestionPort


class CommandSuggestionAdapter(CommandSuggestionPort):
    """
    Finds the commands closest to what a user typed.

    The catalogue is the command tree itself — the same paths the executable
    prints when asked what it answers to — so a suggestion is always a form
    the CLI really accepts, and a command added later is suggestable without
    anyone maintaining a list. An executable that re-exports another one's
    commands declares that other name as an alias, so a usage string
    authored elsewhere is read as its own.

    Only the shape of the invocation is compared: the component and the
    flags. Values are dropped, because the catalogue holds none and a
    container named ``obra`` says nothing about which command was meant.
    """

    NO_EXCLUDED_COMMAND_IDS: ClassVar[Tuple[str, ...]] = ()
    SEPARATOR: ClassVar[str] = " "
    ALTERNATIVE_SEPARATOR: ClassVar[str] = "|"
    MINIMUM_SIMILARITY: ClassVar[float] = 0.5
    SAME_COMPONENT_BONUS: ClassVar[float] = 0.5
    SUGGESTION_LIMIT: ClassVar[int] = 3

    def __init__(
        self,
        executable: str = "ontobdc",
        root_package: str = "ontobdc",
        executable_aliases: Tuple[str, ...] = (),
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._executable: str = executable
        self._root_package: str = root_package
        self._executable_aliases: Tuple[str, ...] = executable_aliases
        self._logger: LogRepositoryPort = logger or NullLogRepository()

    def suggest(self, command_args: List[str]) -> List[str]:
        """
        Return the commands closest to the given arguments, best first.

        A shape the catalogue already holds is answered with nothing: the
        invocation was recognised and failed on something else — a missing
        or malformed value — so proposing other commands would point the
        reader away from the one they had right.
        """
        typed_shape: List[str] = self._shape_of(command_args)
        if not typed_shape:
            return []

        catalogue: List[List[str]] = self._catalogue()
        if typed_shape in catalogue:
            return []

        scored: List[Tuple[float, str]] = []
        path: List[str]
        for path in catalogue:
            score: float = self._score(typed_shape, path)
            if score < self.MINIMUM_SIMILARITY:
                continue

            scored.append((score, self._as_invocation(path)))

        scored.sort(key=lambda candidate: (-candidate[0], candidate[1]))

        return [invocation for _, invocation in scored[:self.SUGGESTION_LIMIT]]

    def _catalogue(self) -> List[List[str]]:
        """
        Return every command form the executable answers to.

        Nothing is excluded, unlike the rendered tree: the base command is
        hidden there because it *is* the tree, but ``--help`` is the first
        thing to point a lost reader at.
        """
        paths: List[List[str]] = CommandTreeAdapter(
            logger=self._logger,
            root_package=self._root_package,
            executable=self._executable,
            excluded_command_ids=self.NO_EXCLUDED_COMMAND_IDS,
            executable_aliases=self._executable_aliases,
        ).discover_command_paths()

        return [
            [self._clean(token) for token in path if self._clean(token)]
            for path in paths
        ]

    @classmethod
    def _clean(cls, token: str) -> str:
        """
        Return the token without the colouring the tree renders it with.

        A token that spells out alternatives — ``--list | -l`` — keeps only
        the first, which is the form to suggest.
        """
        plain: str = TerminalColor.ANSI_ESCAPE_REGEX.sub("", token).strip()

        return plain.split(cls.ALTERNATIVE_SEPARATOR)[0].strip()

    @staticmethod
    def _shape_of(command_args: List[str]) -> List[str]:
        """
        Return the component and the flags, dropping the values between them.
        """
        shape: List[str] = []
        position: int
        argument: str
        for position, argument in enumerate(command_args):
            token: str = argument.strip()
            if not token:
                continue
            if position == 0 or token.startswith("-"):
                shape.append(token)

        return shape

    def _score(self, typed_shape: List[str], path: List[str]) -> float:
        """
        Return how close a catalogue form is to what the user typed.

        Naming the right component and missing a flag is the common mistake,
        so a form under the component that was typed is scored above one
        that merely reads alike.
        """
        if not path:
            return 0.0

        similarity: float = SequenceMatcher(
            None,
            self.SEPARATOR.join(typed_shape),
            self.SEPARATOR.join(path),
        ).ratio()

        if typed_shape[0] == path[0]:
            similarity += self.SAME_COMPONENT_BONUS

        return similarity

    def _as_invocation(self, path: List[str]) -> str:
        """
        Return the catalogue form as the user would type it.
        """
        return self.SEPARATOR.join([self._executable] + path)
