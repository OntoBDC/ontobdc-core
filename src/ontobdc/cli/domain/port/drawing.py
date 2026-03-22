
from typing import Protocol
from abc import ABC, abstractmethod


class DrawingObject(ABC):

    @property
    @abstractmethod
    def length(self) -> int:
        ...

    @property
    @abstractmethod
    def x_pos(self) -> int:
        ...

    @property
    @abstractmethod
    def y_pos(self) -> int:
        ...

    @property
    def left_margin(self) -> str:
        space: str = ""
        while len(space) < self.x_pos:
            space += " "

        return space

    @abstractmethod
    def get_line(self, line_number: int) -> str:
        ...

    @abstractmethod
    def insert_above(line: str) -> str:
        ...


class WireframeDrawingObject(DrawingObject):

    def __init__(self, x_pos: int, y_pos: int):
        self._x_pos: int = x_pos
        self._y_pos: int = y_pos

    @property
    def x_pos(self) -> int:
        return self._x_pos

    @property
    def y_pos(self) -> int:
        return self._y_pos + self._y_offset

    @property
    def _y_offset(self) -> int:
        return 1

    def insert_above(self, lower_layer: str, line_number: int) -> str:
        upper_layer: str = self.get_line(line_number)
        if len(lower_layer) == 0:
            return upper_layer

        if len(lower_layer) < len(upper_layer):
            lower_layer = lower_layer + (" " * (len(upper_layer) - len(lower_layer)))

        line = list(lower_layer)
        for pos, char in enumerate(upper_layer):
            if char != " ":
                line[pos] = char

        return "".join(line)


class WireframeCharacterSet(Protocol):
    vertical: str
    horizontal: str
    corner_top_left: str
    corner_top_right: str
    corner_bottom_left: str
    corner_bottom_right: str
    diagonal_down: str
    diagonal_up: str
    arrow_head_right: str
    transparent: str
