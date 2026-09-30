from dataclasses import dataclass


@dataclass(frozen=True)
class HealthCheck:
    """
    One verification a health check capability reports.

    A check says what it looked at and whether it found it in order. It
    carries no repair and no advice: what to do about a failing check is
    the caller's business, and reporting is the whole of this one's.

    ``scope`` names the subject a check is about when the capability
    reports on more than one — each dataset of a container, say. It is
    empty for a check about the subject the capability was asked about.
    """

    identifier: str
    label: str
    passed: bool
    scope: str = ""
