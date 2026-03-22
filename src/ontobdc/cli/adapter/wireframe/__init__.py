
from dataclasses import dataclass


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
    transparent: str = " "
