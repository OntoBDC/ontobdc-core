from typing import Optional, Tuple
from pathlib import Path
import mimetypes


class FileMimeDetector:
    """Identify MIME during extraction, deriving unknown types from their suffix."""

    @staticmethod
    def of(source_path: str) -> Tuple[Optional[str], Optional[str]]:
        mime: Optional[str]
        encoding: Optional[str]
        mime, encoding = mimetypes.guess_type(source_path)
        if mime is None:
            extension: str = Path(source_path).suffix.lstrip(".").lower()
            if extension:
                mime = f"application/vnd.{extension}"
        return mime, encoding
