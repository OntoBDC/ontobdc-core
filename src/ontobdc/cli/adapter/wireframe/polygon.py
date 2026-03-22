
from __future__ import annotations

from abc import abstractmethod
from typing import Optional
from ontobdc.cli.adapter.wireframe import LightWireframeCharacterSet
from ontobdc.cli.domain.port.drawing import WireframeCharacterSet, WireframeDrawingObject


class Hexagon(WireframeDrawingObject):
    def __init__(
        self,
        x_pos: int,
        y_pos: int,
        character_set: WireframeCharacterSet
    ) -> None:
        self._characters: WireframeCharacterSet = character_set
        super().__init__(x_pos, y_pos)

    @property
    def side(self) -> int:
        return self._side

    @property
    def _y_offset(self) -> int:
        return 0

    def get_line(self, line_number: int) -> str:
        if line_number <= self.y_pos:
            return ""

        content: str = self.left_margin

        if line_number == 1:
            content += self._get_first_line()
        elif line_number == self.height:
            content += self._get_last_line()
        else:
            content += self._get_middle_line()

        return content

    @abstractmethod
    def _get_first_line(self) -> str:
        ...

    @abstractmethod
    def _get_last_line(self) -> str:
        ...

    @abstractmethod
    def _get_middle_line(self) -> str:
        ...


class WideHexagon(Hexagon):
    def __init__(
                self,
                width: int,
                x_pos: int = 0,
                y_pos: int = 0,
                character_set: Optional[WireframeCharacterSet] = None,
            ) -> None:

        self._width: int = width

        if width % 3 != 0:
            raise ValueError("Width value must be a multiple of 3")

        self._height: int = width

        super().__init__(x_pos, y_pos, character_set or LightWireframeCharacterSet())

        self._side = self._width / 3

    @property
    def height(self) -> int:
        return 2 * self._side

    @property
    def length(self) -> int:
        return self.x_pos + 3 * (self._side)

    def _get_first_line(self) -> str:
        content: str = ""
        
        while len(content) <= self.side:
            content += self._characters.transparent

        content += self._characters.horizontal

        return content

    def _get_last_line(self) -> str:
        content: str = ""
        
        while len(content) <= self.side:
            content += self._characters.transparent

        content += self._characters.horizontal

        return content

    def _get_middle_line(self) -> str:
        content: str = ""
        return content


class LongHexagon(Hexagon):

    class _AsciiWireframeCharacterSet(LightWireframeCharacterSet):
        def __init__(self) -> None:
            super().__init__(vertical="|", diagonal_down="\\", diagonal_up="/")

    def __init__(
                self,
                height: int,
                x_pos: int = 0,
                y_pos: int = 0,
                character_set: Optional[WireframeCharacterSet] = None,
            ) -> None:

        if height % 3 != 0:
            raise ValueError("Height value must be a multiple of 3")

        self._height: int = height
        self._side = self._height / 3

        if self._side == 1:
            character_set: WireframeCharacterSet = character_set or self._AsciiWireframeCharacterSet()
        else:
            character_set: WireframeCharacterSet = character_set or LightWireframeCharacterSet()

        super().__init__(x_pos, y_pos, character_set)

    @property
    def height(self) -> int:
        return 3 * self._side

    @property
    def length(self) -> int:
        return self.x_pos + 2 * (self._side)

    def get_line(self, line_number: int) -> str:
        if line_number <= self.y_pos:
            return ""

        content: str = self.left_margin

        if line_number == 1:
            content += self._get_first_line()
        elif line_number <= self.side:
            content += self._get_top_line(line_number)
        # elif line_number == self.height:
        #     content += self._get_last_line()
        # else:
        #     content += self._get_middle_line()

        return content

    def _get_first_line(self) -> str:
        content: str = ""
        
        while len(content) < self.side:
            content += self._characters.transparent

        content += self._characters.diagonal_up
        content += self._characters.diagonal_down

        return content

    def _get_last_line(self) -> str:
        content: str = ""
        
        while len(content) < self.side:
            content += self._characters.transparent

        content += self._characters.diagonal_down
        content += self._characters.diagonal_up

        return content

    def _get_middle_line(self) -> str:
        content: str = self._characters.vertical

        while len(content) <= 2 * self.side:
            content += self._characters.transparent

        content += self._characters.vertical

        return content

    def _get_top_line(self, line_number: int) -> str:
        content: str = ""
        offset: int = self.side

        while len(content) <= offset - line_number:
            content += self._characters.transparent

        content += self._characters.diagonal_up

        print(line_number, self.side, offset)
        while len(content) + line_number + 1 <= line_number * self.side:
            content += self._characters.transparent

        content += self._characters.diagonal_down

        return content
