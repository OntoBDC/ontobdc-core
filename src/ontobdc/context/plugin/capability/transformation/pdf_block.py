from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import pymupdf

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.etl import EtlEventPayloadKeys
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class PdfBlockExtractionCapability(TransformationCapability):
    """
    Extracts positioned text blocks from every page of a PDF document and
    returns them as a structured list, one entry per page, each carrying
    the page geometry and every block's bounding box plus textual payload.

    Only blocks whose ``block_type`` is ``0`` (plain text) are kept. Images,
    drawings and vector artefacts are intentionally dropped because this
    capability acts as the canonical upstream source for every later
    semantic stage of the Context layer: chunk splitting, section
    detection, header/footer stripping, typification and named-entity
    extraction all consume the block list this capability produces.

    When ``OUTPUT_PATH_KEY`` is provided in the context, the full block
    payload is persisted as a UTF-8 JSON document and the returned content
    carries the persisted path alongside the usual page/block counts.
    """

    SOURCE_PATH_KEY: ClassVar[str] = EtlEventPayloadKeys.SOURCE_PATH
    OUTPUT_PATH_KEY: ClassVar[str] = "output_path"

    PAGE_COUNT_KEY: ClassVar[str] = "page_count"
    BLOCK_COUNT_KEY: ClassVar[str] = "block_count"
    PAGES_KEY: ClassVar[str] = "pages"
    WRITTEN_TO_KEY: ClassVar[str] = "written_to"

    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.pdf_block_extraction",
        version="1.0.0",
        name="PDF Block Extraction",
        description=(
            "Extract positioned text blocks from a PDF document using "
            "PyMuPDF's get_text('blocks') routine, keeping only plain-text "
            "blocks and discarding images and drawing artefacts. "
            "When an output_path parameter is supplied, the block payload is "
            "persisted as JSON before the response is returned."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ontobdc", "context", "pdf", "text", "block", "transformation"],
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
                    "description": "Optional file path where the full block payload "
                    "will be written as UTF-8 JSON.",
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
                BLOCK_COUNT_KEY: {
                    "type": "integer",
                },
                PAGES_KEY: {
                    "type": "array",
                    "description": "Present only when no OUTPUT_PATH_KEY was supplied.",
                },
                WRITTEN_TO_KEY: {
                    "type": "string",
                    "description": "Present only when OUTPUT_PATH_KEY was supplied and the payload was persisted.",
                },
            },
        },
        log_message={
            "info": {
                "en": "PDF text blocks were extracted.",
                "pt-br": "Os blocos de texto do PDF foram extraídos.",
            },
            "debug_entry": {
                "en": "Extracting positioned text blocks from the provided PDF document.",
                "pt-br": "Extraindo blocos de texto posicionados do documento PDF fornecido.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Extração de blocos do PDF"
        return "PDF block extraction"

    def description(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Extrai blocos de texto posicionados de um PDF com PyMuPDF."
        return "Extract positioned text blocks from a PDF with PyMuPDF."

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
            and isinstance(payload.get(self.BLOCK_COUNT_KEY), int)
            and int(payload[self.BLOCK_COUNT_KEY]) >= 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_path: str = RequiredParameter.of(context, self.SOURCE_PATH_KEY)
        source_path: Path = Path(raw_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"Invalid PDF path: {source_path}")
        if source_path.suffix.lower() != ".pdf":
            suffix = source_path.suffix or "<none>"
            raise ValueError(f"Expected a PDF file, got: '{suffix}'")

        pages: List[Dict[str, Any]] = []
        block_count: int = 0

        document = pymupdf.open(source_path)
        try:
            page_index: int
            for page_index, page in enumerate(document):
                page_blocks: List[Dict[str, Any]] = []

                raw_block: Any
                for raw_block in page.get_text("blocks"):
                    x0, y0, x1, y1, text, block_number, block_type = raw_block[:7]

                    if int(block_type) != 0:
                        continue

                    block: Dict[str, Any] = {
                        "block_number": int(block_number),
                        "block_type": int(block_type),
                        "bbox": [float(x0), float(y0), float(x1), float(y1)],
                        "text": str(text),
                    }
                    page_blocks.append(block)
                    block_count += 1

                pages.append(
                    {
                        "page": page_index + 1,
                        "width": float(page.rect.width),
                        "height": float(page.rect.height),
                        "blocks": page_blocks,
                    }
                )
        finally:
            document.close()

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
                self.PAGE_COUNT_KEY: len(pages),
                self.BLOCK_COUNT_KEY: block_count,
                self.PAGES_KEY: pages,
            }
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(full_payload, handle, ensure_ascii=False, indent=2)

            return {
                self.SOURCE_PATH_KEY: str(source_path),
                self.PAGE_COUNT_KEY: len(pages),
                self.BLOCK_COUNT_KEY: block_count,
                self.WRITTEN_TO_KEY: str(output_path),
            }

        return {
            self.SOURCE_PATH_KEY: str(source_path),
            self.PAGE_COUNT_KEY: len(pages),
            self.BLOCK_COUNT_KEY: block_count,
            self.PAGES_KEY: pages,
        }

