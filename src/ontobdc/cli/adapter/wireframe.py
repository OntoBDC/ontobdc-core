
from __future__ import annotations
from dataclasses import dataclass
from ontobdc.cli..port.drawing import WireframeCharacterSet, WireframeDrawingObject


@dataclass(frozen=True)
class LightWireframeCharacterSet:
    vertical: str = "│"
    horizontal: str = "─"
    corner_top_left: str = "┌"
    corner_top_right: str = "┐"
    corner_bottom_left: str = "└"
    corner_bottom_right: str = "┘"
    diagonal_down: str = "╲"
    diagonal_up: str = "╱"
    arrow_head_right: str = "❯"


class Rectangle(WireframeDrawingObject):

    def __init__(self,  width: int,
                        height: int,
                        x_pos: int = 0,
                        y_pos: int = 0,
                        character_set: WireframeCharacterSet = None
                    ) -> None:
        self._height: int = height
        self._width: int = width
        self._characters: WireframeCharacterSet = character_set or LightWireframeCharacterSet()
        super().__init__(x_pos, y_pos)

    @property
    def length(self) -> int:
        return self._x_pos + self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def y_pos(self) -> int:
        return self._y_pos

    def get_line(self, line_number: int) -> str:
        content: str = self.left_margin

        if line_number == 1:
            content += self._get_first_line()
        elif line_number == self.height:
            content += self._get_last_line()
        else:
            content += self._get_middle_line()

        return content

    def _get_first_line(self) -> str:
        content: str = self._characters.corner_top_left
        while len(content) < (self._width * 2):
            content += self._characters.horizontal * 2

        return content + self._characters.corner_top_right

    def _get_middle_line(self) -> str:
        content: str = self._characters.vertical + " "
        while len(content) < (self._width * 2):
            content += "  "

        content += " " + self._characters.vertical

        return content

    def _get_last_line(self) -> str:
        content: str = self._characters.corner_bottom_left + self._characters.horizontal
        while len(content) < (self._width * 2):
            content += self._characters.horizontal * 2

        content += self._characters.horizontal + self._characters.corner_bottom_right

        return content


class RightArrow(WireframeDrawingObject):

    def __init__(self,  height: int,
                        x_pos: int = 0,
                        y_pos: int = 0,
                        rotation: int = 0,
                        angle: int = 90,
                        character_set: WireframeCharacterSet = None
                    ) -> None:
        self._height: int = height
        self._middle: int = self._height // 2 + 1
        self._rotation: int = rotation
        self._characters: WireframeCharacterSet = character_set or LightWireframeCharacterSet()
        super().__init__(x_pos, y_pos)

    @property
    def width(self) -> int:
        return self._middle

    @property
    def length(self) -> int:
        return self._x_pos + self.width

    @property
    def height(self) -> int:
        return self._height

    def get_line(self, line_number: int) -> str:
        if line_number <= self.y_pos:
            return ""

        content: str = self.left_margin

        if line_number == self._middle + self.y_pos and self._middle % 2 != 0:
            while len(content) - self.x_pos < (line_number - self._middle + self.y_pos):
                content += " "

            content += self._characters.arrow_head_right
        elif line_number < self._middle + self.y_pos and self._middle % 2 != 0:
            while len(content) - self.x_pos < (line_number - self._middle + self.y_pos):
                content += " "

            content += self._characters.diagonal_down
        elif line_number < self._middle + self.y_pos:
            while len(content) - self.x_pos < (line_number - self._middle + self.y_pos + 1):
                content += " "

            content += self._characters.diagonal_down
        else:
            while (len(content) - self.x_pos < self.height + self.y_pos - line_number):
                content += " "

            content += self._characters.diagonal_up

        return content
