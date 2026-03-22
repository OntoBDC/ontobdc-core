
from typing import Dict, List
from ontobdc.cli.domain.port.drawing import DrawingObject


class Canvas:
    def __init__(self, width: int = 0, height: int = 0) -> None:
        self._width: int = 0
        self._height: int = 0
        self._drawing_objects: List[DrawingObject] = []

    def print(self) -> None:

        print("")
        for line in self.build():
            print(line)

        print("")

    def add_drawing_object(self, drawing_object: DrawingObject):
        self._drawing_objects.append(drawing_object)

    def build(self) -> List[str]:
        if self._width < 5:
            for draw_obj in self._drawing_objects:
                if draw_obj.length > self._width:
                    self._width = draw_obj.length

        if self._height < 2:
            for draw_obj in self._drawing_objects:
                if draw_obj.height > self._height:
                    self._height = draw_obj.height

        content: Dict[int, str] = {}
        line_number: int = len(content) + 1

        while line_number <= self._height + 1:
            content[line_number] = ""
            for draw_obj in self._drawing_objects:
                if line_number <= draw_obj.height + draw_obj.y_pos:
                    content[line_number] = self._combine_line(content[line_number], draw_obj, line_number)
            line_number += 1

        return list(content.values())

    def _combine_line(self, lower_layer: str, draw_obj: DrawingObject, line_number: int):
        return draw_obj.insert_above(lower_layer, line_number)
