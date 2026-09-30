"""Storage transformation capabilities — shared contract constants.

This module re-exports the shared ETL event contract from
:mod:`ontobdc.shared.adapter.etl` and extends it with the
canonical module/phase/entity fragment names used by every storage
transformation capability.  Storage transformation states are always rooted
at the ``file`` entity of the ``context`` module inside the ``suggestion``
phase (see the ``file_meaning_suggestion`` FSM).
"""

import re
from typing import ClassVar, Dict

from ontobdc.shared.adapter.etl import (
    EtlDirectoryContract,
    EtlEventContextKeys,
    EtlEventPayloadKeys,
    EtlLanguageContract,
    EtlPatterns,
)

ETL_MODULE_NAME: ClassVar[str] = "context"
ETL_PHASE_NAME: ClassVar[str] = "suggestion"
ETL_ENTITY_NAME: ClassVar[str] = "file"

ETL_DIRECTORY_NAME: ClassVar[str] = EtlDirectoryContract.DIRECTORY_NAME
CONTAINER_PATH_KEY: ClassVar[str] = EtlEventContextKeys.CONTAINER_PATH
SOURCE_PATH_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.SOURCE_PATH
NORMALIZED_PATH_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.NORMALIZED_PATH
RO_CRATE_HASH_KEY: ClassVar[str] = EtlEventPayloadKeys.RO_CRATE_HASH
WHITESPACE_PATTERN: ClassVar[re.Pattern[str]] = EtlPatterns.WHITESPACE
MIME_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.MIME
METADATA_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.METADATA
EVALUATION_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.EVALUATION
CONTENT_SIZE_KEY: ClassVar[str] = EtlEventPayloadKeys.CONTENT_SIZE
DATE_MODIFIED_KEY: ClassVar[str] = EtlEventPayloadKeys.DATE_MODIFIED
DATE_CREATED_KEY: ClassVar[str] = EtlEventPayloadKeys.DATE_CREATED
LANGUAGE_CODES: ClassVar[Dict[str, str]] = EtlLanguageContract.CODES
LANGUAGE_RESULT_KEY: ClassVar[str] = EtlLanguageContract.RESULT_KEY
LEMMA_RESULT_KEY: ClassVar[str] = EtlEventPayloadKeys.LEMMA

__all__ = [
    "CONTAINER_PATH_KEY",
    "CONTENT_SIZE_KEY",
    "DATE_CREATED_KEY",
    "DATE_MODIFIED_KEY",
    "ETL_DIRECTORY_NAME",
    "ETL_ENTITY_NAME",
    "ETL_MODULE_NAME",
    "ETL_PHASE_NAME",
    "EtlDirectoryContract",
    "EtlEventContextKeys",
    "EtlEventPayloadKeys",
    "EtlLanguageContract",
    "EtlPatterns",
    "EVALUATION_RESULT_KEY",
    "LANGUAGE_CODES",
    "LANGUAGE_RESULT_KEY",
    "LEMMA_RESULT_KEY",
    "METADATA_RESULT_KEY",
    "MIME_RESULT_KEY",
    "NORMALIZED_PATH_RESULT_KEY",
    "RO_CRATE_HASH_KEY",
    "SOURCE_PATH_RESULT_KEY",
    "WHITESPACE_PATTERN",
]
