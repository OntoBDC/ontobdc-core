
from __future__ import annotations

from typing import Optional
from ontobdc.cli.adapter.wireframe import LightWireframeCharacterSet
from ontobdc.cli.domain.port.drawing import WireframeCharacterSet, WireframeDrawingObject


class Rectangle(WireframeDrawingObject):

    def __init__(self,  width: int,
                        height: int,
                        x_pos: int = 0,
                        y_pos: int = 0,
                        character_set: Optional[WireframeCharacterSet] = None
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
    def _y_offset(self) -> int:
        return 0

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
