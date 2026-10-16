from datetime import datetime


class CurrentDateTimeGenerator:
    """
    ``facade:CurrentDateTimeGenerator``: the date and time of the moment, to
    the second, as the data sources of entities hold them
    (``2026-10-05T18:33:53``).
    """

    @staticmethod
    def generate() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
