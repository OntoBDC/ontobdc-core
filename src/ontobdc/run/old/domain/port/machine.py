
from enum import Enum
from abc import abstractmethod


class IntentStatePort(str, Enum):
    """
    Enum representing the possible states of the capability intent resolution process.

    Matches the states referenced in the pipeline and follows the
    localization pattern.
    """
    ...
