

from typing import Optional
from dataclasses import dataclass


@dataclass
class BaseResource:
    """
    Base resource.
    """
    id: str
    name: str
    description: Optional[str] = None



