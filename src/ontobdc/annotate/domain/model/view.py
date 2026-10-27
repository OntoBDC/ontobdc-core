import base64
import binascii
from typing import ClassVar


class AnnotationView:
    """
    The picture of the document an annotation is made on as the person left it: a model in space, seen from where they
    chose, with the shapes they put in it. It is a PNG, kept beside the annotation under its global id, and it travels
    in a command as the text of its bytes.
    """

    SUFFIX: ClassVar[str] = ".png"
    SIGNATURE: ClassVar[bytes] = b"\x89PNG\r\n\x1a\n"

    @classmethod
    def file_name(cls, guid: str) -> str:
        return f"{guid}{cls.SUFFIX}"

    @classmethod
    def decode(cls, text: str) -> bytes:
        """
        The bytes of the picture from the text that carries them.

        Raises:
            ValueError: the text is not the bytes of a PNG.
        """
        try:
            data: bytes = base64.b64decode(text.strip(), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("the view of an annotation is the base64 text of a PNG") from error
        if not data.startswith(cls.SIGNATURE):
            raise ValueError("the view of an annotation is the base64 text of a PNG")

        return data
