from typing import Optional

ENGLISH_NLP_MODEL_NAME: str = "en_core_web_sm"


def main(root_path: Optional[str] = None) -> int:
    """
    Return 0 when the small English spaCy model is installed, 1 otherwise.

    ``root_path`` is accepted only to match the ``main(root_path) -> int``
    contract every other CLI init check follows -- the spaCy model is a
    Python-environment resource, not a per-project one.
    """
    try:
        import spacy.util

        return 0 if spacy.util.is_package(ENGLISH_NLP_MODEL_NAME) else 1
    except Exception:
        return 1
