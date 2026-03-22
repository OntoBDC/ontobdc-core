
from __future__ import annotations

from typing import Optional
from ontobdc.cli.adapter.wireframe import LightWireframeCharacterSet
from ontobdc.cli.domain.port.drawing import WireframeCharacterSet, WireframeDrawingObject


class RightArrow(WireframeDrawingObject):

    def __init__(self,  height: int,
                        x_pos: int = 0,
                        y_pos: int = 0,
                        rotation: int = 0,
                        angle: int = 90,
                        character_set: Optional[WireframeCharacterSet] = None
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
