"""Centralized ETL event and persisted-state contract helpers.

The OntoBDC ETL directory layout is shared across domain modules (storage,
context, container) and follows the canonical shape::

    <root_marker>/.__ontobdc__/etl/<module>/<phase>/<entity>/<state>.json

All contracts exposed by this module are encapsulated into
single-responsibility namespace classes, matching how
:mod:`ontobdc.shared.adapter.ontology` separates resource locators from
config adapters and :mod:`ontobdc.shared.adapter.config` keeps config
data and unset-project-root adapters in dedicated types.

No module-level constants are exposed; every consumer must import the
relevant class and access its :class:`ClassVar` attributes.  This keeps
refactors traceable (a typped attribute access fails with
``AttributeError`` at import time, not as a silent ``KeyError`` at
runtime) and the file listing small even when the contract grows.
"""

import re
from typing import ClassVar, Dict


class EtlEventContextKeys:
    """Keys the shared ``CliContextPort`` carries between stages.

    A capability reads its input from the context using one of these
    names and/or writes its output back so the next capability in the
    pipeline can locate it without having to hardcode a string. Keeping
    the names in a class means typos become ``AttributeError`` at import
    time, not a silent ``None`` at runtime.
    """

    CONTAINER_PATH: ClassVar[str] = "container_path"


class EtlEventPayloadKeys:
    """Keys present inside the JSON payload a capability produces.

    Two capabilities or a capability + a renderer need to agree on these
    strings for a consumer to read a persisted event without importing
    the producer's private plugin package. Mapping every shared key here
    keeps the contract visible in one place.
    """

    SOURCE_PATH: ClassVar[str] = "source_path"
    NORMALIZED_PATH: ClassVar[str] = "normalized_path"
    RO_CRATE_HASH: ClassVar[str] = "ro-crate-hash"
    MIME: ClassVar[str] = "mime"
    METADATA: ClassVar[str] = "metadata"
    LANGUAGE: ClassVar[str] = "language"
    EVALUATION: ClassVar[str] = "evaluation"
    CONTENT_SIZE: ClassVar[str] = "contentSize"
    DATE_MODIFIED: ClassVar[str] = "dateModified"
    DATE_CREATED: ClassVar[str] = "dateCreated"
    LEMMA: ClassVar[str] = "lemma"


class EtlDirectoryContract:
    """Canonical filesystem fragment used by every persisted ETL event.

    Module/phase/entity fragments remain local to each domain's plugin
    package (``ETL_MODULE_NAME``, ``ETL_PHASE_NAME``, ``ETL_ENTITY_NAME``
    declared in ``storage.plugin.capability.transformation`` and the
    equivalent packages for ``context``, ``container``, …) because each
    domain owns its own fragment value. Only the directory name that
    lives directly under ``.__ontobdc__/`` is shared.
    """

    DIRECTORY_NAME: ClassVar[str] = "etl"


class EtlLanguageContract:
    """Normalized language code map + shared result key.

    Lemma/tag pipelines emit two-letter tokens (``en``, ``pt``) but
    UI/suggestion layers consume the four-letter ``xx-xx`` variant
    (``en``, ``pt-br``). The mapping is centralized here so a new
    language pair is added in exactly one place.
    """

    RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.LANGUAGE

    CODES: ClassVar[Dict[str, str]] = {
        "en": "en",
        "pt": "pt-br",
    }


class EtlPatterns:
    """Shared compiled regular expressions.

    Compiling them once in the contract avoids rebuilding the same
    ``Pattern`` object inside every capability/tokenizer call.
    """

    WHITESPACE: ClassVar[re.Pattern[str]] = re.compile(r"\s+")
