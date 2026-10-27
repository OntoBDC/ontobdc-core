from typing import List


class OffsetText:
    """
    How far a geometry is moved, as the command line gives it: one number for each coordinate, separated by commas
    (``0.1,-0.05``).
    """

    @staticmethod
    def numbers(text: str) -> List[float]:
        try:
            return [float(part) for part in text.split(",")]
        except ValueError as error:
            raise ValueError(f"an offset is numbers separated by commas, such as 0.1,-0.05: {text!r}") from error
