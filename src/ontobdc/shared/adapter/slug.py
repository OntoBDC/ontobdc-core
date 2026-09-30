import re
from typing import ClassVar, Pattern
import unicodedata


class TitleSlug:
    """
    Turns a title into the directory name that holds what it names.

    The title is what a reader sees, kept as given in the metadata; the slug
    is what the filesystem sees, so it carries no accent, no space and no
    character that would need quoting in a shell. Datasets and projects are
    both named this way, which is why this does not belong to either.
    """

    SEPARATOR: ClassVar[str] = "-"
    _COMBINING_CATEGORY: ClassVar[str] = "Mn"
    _NON_ALPHANUMERIC: ClassVar[Pattern[str]] = re.compile(r"[^a-z0-9]+")
    _REPEATED_SEPARATOR: ClassVar[Pattern[str]] = re.compile(r"-{2,}")

    @classmethod
    def of(cls, title: str) -> str:
        """
        Return the slug of the given title, or an empty string when it has no
        usable character.
        """
        decomposed: str = unicodedata.normalize("NFKD", title.strip())
        unaccented: str = "".join(
            character
            for character in decomposed
            if unicodedata.category(character) != cls._COMBINING_CATEGORY
        )
        separated: str = cls._NON_ALPHANUMERIC.sub(cls.SEPARATOR, unaccented.lower())

        return cls._REPEATED_SEPARATOR.sub(cls.SEPARATOR, separated).strip(cls.SEPARATOR)
