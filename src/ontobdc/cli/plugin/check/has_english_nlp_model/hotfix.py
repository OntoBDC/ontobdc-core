from typing import Optional

from ontobdc.cli.plugin.check.has_english_nlp_model.check import ENGLISH_NLP_MODEL_NAME


def main(root_path: Optional[str] = None) -> int:
    """
    Download the small English spaCy model if it is missing.

    ``root_path`` is accepted only to match the ``main(root_path) -> int``
    contract every other CLI init hotfix follows.
    """
    try:
        import spacy.util

        if spacy.util.is_package(ENGLISH_NLP_MODEL_NAME):
            return 0

        from spacy.cli import download as spacy_download

        spacy_download(ENGLISH_NLP_MODEL_NAME)

        return 0 if spacy.util.is_package(ENGLISH_NLP_MODEL_NAME) else 1
    except Exception:
        return 1
