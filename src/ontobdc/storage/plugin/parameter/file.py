from pathlib import Path
from typing import Any, Optional

from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort


class FileIdStrategy(CliContextStrategyPort):
    """
    Resolve the file selector a command declares to an identifier and a path.

    A user names a file the way they have it at hand: the global identifier
    the graph knows it by, or the path it occupies on disk. A selector that
    names an existing file resolves to that path; anything else is taken as
    the global identifier of a file the graph knows. Only one of the two is
    resolved from a selector, so the other stays unset rather than guessed.
    """

    SELECTOR_FLAG: str = "--file"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.ontobdc.storage.plugin.parameter.file",
        version="1.0.0",
        name="file",
        description=(
            "Resolve --file, given as a global identifier or a filesystem "
            "path, to the file it selects."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=Path,
        tags=["storage", "file", "identifier"],
        supported_languages=["en", "pt-br"],
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind the file the declared selector names, or clear a stale binding.
        """
        if self.SELECTOR_FLAG not in context.raw_args:
            return context

        selector: Optional[str] = self._selector(context)
        if selector is None:
            self._clear(context)
            return context

        candidate: Path = Path(selector).expanduser()
        if candidate.is_file():
            self._bind(context, file_id=None, file_path=candidate.resolve())
            return context

        self._bind(context, file_id=selector, file_path=None)

        return context

    @staticmethod
    def _selector(context: CliContextPort) -> Optional[str]:
        """
        Return the selector the user typed, or None when they typed none.
        """
        value: Any = context.get_parameter_value("file")
        if not isinstance(value, str):
            return None

        selector: str = value.strip()
        if not selector:
            return None

        return selector

    @staticmethod
    def _bind(
        context: CliContextPort,
        file_id: Optional[str],
        file_path: Optional[Path],
    ) -> None:
        """
        Write what the selector resolved to, dropping what it did not.
        """
        if file_id is None:
            context.delete_parameter("file_id")
        else:
            context.set_parameter_value("file_id", file_id)

        if file_path is None:
            context.delete_parameter("file_path")
        else:
            context.set_parameter_value("file_path", str(file_path))

    @staticmethod
    def _clear(context: CliContextPort) -> None:
        """
        Drop a file resolved by an earlier invocation.

        Leaving it in place would let a command that named no file, or named
        an empty one, silently operate on whatever file came before it.
        """
        context.delete_parameter("file_id")
        context.delete_parameter("file_path")
