
import re
from typing import ClassVar, Dict, List, Tuple

from ontobdc.storage.plugin.capability.transformation import (
    WHITESPACE_PATTERN,
)


class TokenStatisticsTokenizer:
    """
    Deterministic whitespace tokenizer for lemmatized path strings.

    Produces an ordered token sequence and flags each token as lexical
    (natural-language word) or identifier-like (numeric, drawing number,
    revision fragment, etc.). Identifier tokens are retained and counted
    (per spec: the statistic state must not discard them) but marked so
    later semantic stages can ignore them by default when convenient.
    """

    BOS: ClassVar[str] = "__BOS__"
    EOS: ClassVar[str] = "__EOS__"
    IDENTIFIER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(\d[\d\.\-]*|[A-Za-z]{1,3}\d.*|[A-Za-z]?\d+[A-Za-z]?)$"
    )

    @classmethod
    def tokenize(cls, lemma: str) -> Tuple[List[str], Dict[str, bool]]:
        """
        Return ``(ordered_tokens, is_identifier_map)``.

        ``ordered_tokens`` always includes the analytical boundary markers
        ``__BOS__`` and ``__EOS__`` as first and last positions.

        ``is_identifier_map`` maps every distinct non-boundary token to a
        boolean flag. ``True`` means the token is numeric or identifier-
        like; ``False`` means it is a lexical word.
        """
        cleaned: str = WHITESPACE_PATTERN.sub(" ", lemma.strip()).strip()
        if not cleaned:
            return ([cls.BOS, cls.EOS], {})

        raw_tokens: List[str] = cleaned.split(" ")
        is_identifier_map: Dict[str, bool] = {}
        token: str
        for token in raw_tokens:
            if token in is_identifier_map:
                continue
            is_identifier_map[token] = bool(cls.IDENTIFIER_PATTERN.match(token))

        ordered: List[str] = [cls.BOS]
        ordered.extend(raw_tokens)
        ordered.append(cls.EOS)

        return (ordered, is_identifier_map)

