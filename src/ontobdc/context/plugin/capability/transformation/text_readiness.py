from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

import pymupdf

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.etl import EtlEventPayloadKeys
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class TextReadinessCheckerCapability(TransformationCapability):
    """
    Verifies whether a PDF document contains enough extractable plain text
    to be considered "readable" for downstream knowledge graph authoring.

    Documents that are image-only (scanned pages without OCR) or that carry
    only a handful of textual characters will fail the check and prevent the
    pipeline from proceeding to block extraction and further semantic stages.

    When ``OUTPUT_PATH_KEY`` is provided in the context, the full readiness
    payload is persisted as a UTF-8 JSON document and the returned content
    carries the persisted path alongside the character/image counts.
    """

    SOURCE_PATH_KEY: ClassVar[str] = EtlEventPayloadKeys.SOURCE_PATH
    OUTPUT_PATH_KEY: ClassVar[str] = "output_path"

    PAGE_COUNT_KEY: ClassVar[str] = "page_count"
    TEXT_CHAR_COUNT_KEY: ClassVar[str] = "text_char_count"
    IMAGE_COUNT_KEY: ClassVar[str] = "image_count"
    IS_READABLE_KEY: ClassVar[str] = "is_readable"
    MIN_READABLE_CHARS: ClassVar[int] = 100
    WRITTEN_TO_KEY: ClassVar[str] = "written_to"

    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.text_readiness_checker",
        version="1.0.0",
        name="PDF Text Readiness Check",
        description=(
            "Verify whether a PDF document contains enough extractable plain "
            "text to be considered readable for knowledge graph authoring. "
            "Counts textual characters across all pages using PyMuPDF blocks "
            "and tallies embedded images. A document is considered readable "
            "when its extracted textual character count meets or exceeds the "
            "built-in threshold."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ontobdc", "context", "pdf", "text", "readiness", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                SOURCE_PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
                OUTPUT_PATH_KEY: {
                    "type": "string",
                    "required": False,
                    "description": "Optional file path where the readiness payload will be written as UTF-8 JSON.",
                },
            },
        },
        output_schema={
            "properties": {
                SOURCE_PATH_KEY: {
                    "type": "string",
                },
                PAGE_COUNT_KEY: {
                    "type": "integer",
                },
                TEXT_CHAR_COUNT_KEY: {
                    "type": "integer",
                },
                IMAGE_COUNT_KEY: {
                    "type": "integer",
                },
                IS_READABLE_KEY: {
                    "type": "boolean",
                },
                WRITTEN_TO_KEY: {
                    "type": "string",
                    "description": "Present only when OUTPUT_PATH_KEY was supplied and the payload was persisted.",
                },
            },
        },
        log_message={
            "info": {
                "en": "PDF text readiness was verified.",
                "pt-br": "A legibilidade de texto do PDF foi verificada.",
            },
            "debug_entry": {
                "en": "Verifying whether the provided PDF document contains enough extractable plain text.",
                "pt-br": "Verificando se o documento PDF fornecido contém texto extraível legível suficiente.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Verificação de legibilidade de texto do PDF"
        return "PDF text readiness check"

    def description(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return (
                "Verifica se um PDF contém texto plano extraível suficiente "
                "para a autoria de grafos de conhecimento."
            )
        return (
            "Verify whether a PDF contains enough extractable plain text "
            "for knowledge graph authoring."
        )

    def is_satisfied(self, context: CliContextPort) -> bool:
        raw_path: Optional[str] = RequiredParameter.optional(
            context,
            self.SOURCE_PATH_KEY,
        )
        if raw_path is None:
            return False

        source_path: Path = Path(raw_path).expanduser().resolve()
        if not (
            source_path.exists()
            and source_path.is_file()
            and source_path.suffix.lower() == ".pdf"
        ):
            return False

        raw_output: Optional[str] = RequiredParameter.optional(
            context,
            self.OUTPUT_PATH_KEY,
        )
        if raw_output is None:
            return False

        output_path: Path = Path(raw_output).expanduser().resolve()
        if not output_path.exists() or not output_path.is_file():
            return False

        try:
            import json as _json

            payload: Dict[str, Any] = _json.loads(
                output_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return False

        return (
            payload.get(self.SOURCE_PATH_KEY) == str(source_path)
            and payload.get(self.IS_READABLE_KEY) is True
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_path: str = RequiredParameter.of(context, self.SOURCE_PATH_KEY)
        source_path: Path = Path(raw_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"Invalid PDF path: {source_path}")
        if source_path.suffix.lower() != ".pdf":
            suffix = source_path.suffix or "<none>"
            raise ValueError(f"Expected a PDF file, got: '{suffix}'")

        text_char_count: int = 0
        image_count: int = 0
        page_count: int = 0

        document = pymupdf.open(source_path)
        try:
            page_count = document.page_count
            for page in document:
                raw_block: Any
                for raw_block in page.get_text("blocks"):
                    block_type: int = int(raw_block[6]) if len(raw_block) > 6 else -1
                    if block_type == 0:
                        text: str = str(raw_block[4]) if len(raw_block) > 4 else ""
                        text_char_count += len(text)
                image_count += len(page.get_images(full=True))
        finally:
            document.close()

        is_readable: bool = text_char_count >= self.MIN_READABLE_CHARS

        if not is_readable:
            raise ValueError(
                "PDF does not contain enough extractable plain text to be "
                "considered readable. "
                f"Found {text_char_count} textual characters across "
                f"{page_count} page(s) (minimum required: "
                f"{self.MIN_READABLE_CHARS}). "
                f"Embedded image count: {image_count}. "
                "This typically indicates a scanned or image-only document "
                "that requires OCR before it can be processed by the "
                "knowledge-graph pipeline."
            )

        raw_output_path: Optional[str] = RequiredParameter.optional(
            context,
            self.OUTPUT_PATH_KEY,
        )
        if raw_output_path is not None and str(raw_output_path).strip():
            output_path: Path = Path(raw_output_path).expanduser().resolve()
            parent: Path = output_path.parent
            if not parent.exists() or not parent.is_dir():
                raise ValueError(
                    f"Invalid output directory: {parent}. "
                    f"Directory does not exist or is not a folder."
                )

            full_payload: Dict[str, Any] = {
                self.SOURCE_PATH_KEY: str(source_path),
                self.PAGE_COUNT_KEY: page_count,
                self.TEXT_CHAR_COUNT_KEY: text_char_count,
                self.IMAGE_COUNT_KEY: image_count,
                self.IS_READABLE_KEY: is_readable,
            }
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(full_payload, handle, ensure_ascii=False, indent=2)

            return {
                self.SOURCE_PATH_KEY: str(source_path),
                self.PAGE_COUNT_KEY: page_count,
                self.TEXT_CHAR_COUNT_KEY: text_char_count,
                self.IMAGE_COUNT_KEY: image_count,
                self.IS_READABLE_KEY: is_readable,
                self.WRITTEN_TO_KEY: str(output_path),
            }

        return {
            self.SOURCE_PATH_KEY: str(source_path),
            self.PAGE_COUNT_KEY: page_count,
            self.TEXT_CHAR_COUNT_KEY: text_char_count,
            self.IMAGE_COUNT_KEY: image_count,
            self.IS_READABLE_KEY: is_readable,
        }
