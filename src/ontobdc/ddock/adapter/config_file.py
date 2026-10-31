from pathlib import Path
from typing import Any, Dict, List

import yaml


class ConfigFile:
    """
    The ``asset/config.yaml`` of the source folder, of which a system copies
    whole keys from its ``system.obdc``.

    A key is replaced as a whole, in the place it has in the file when it has
    one and at the end of it when it has not; the rest of the text, comments
    included, is kept as it is.
    """

    @staticmethod
    def read(config: Path) -> Dict[str, Any]:
        if not config.is_file():
            return {}

        data: Any = yaml.safe_load(config.read_text(encoding="utf-8"))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"The configuration must be a mapping: {config}")

        return data

    @classmethod
    def has(cls, config: Path, key: str, value: Any) -> bool:
        """
        Whether the key of the file already says exactly what ``value`` says.
        """
        data: Dict[str, Any] = cls.read(config)
        return key in data and data[key] == value

    @classmethod
    def copy(cls, config: Path, key: str, value: Any) -> None:
        """
        Put ``value`` as the key of the file, whatever the key said before.
        """
        text: str = config.read_text(encoding="utf-8") if config.is_file() else ""
        block: str = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True)
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(cls._replaced(text, key, block), encoding="utf-8")

    @staticmethod
    def _replaced(text: str, key: str, block: str) -> str:
        """
        The text with the top-level ``key`` (from its line up to the next
        top-level key) replaced by ``block``, or with ``block`` at its end when
        the text has no such key.
        """
        result: List[str] = []
        skipping: bool = False
        placed: bool = False
        line: str
        for line in text.splitlines(keepends=True):
            top_level: bool = bool(line.strip()) and not line[0].isspace() and not line.startswith("#")
            if top_level:
                skipping = line.startswith(f"{key}:")
                if skipping and not placed:
                    result.append(block)
                    placed = True
            if not skipping:
                result.append(line)

        if not placed:
            if result and not result[-1].endswith("\n"):
                result.append("\n")
            result.append(block)

        return "".join(result)
