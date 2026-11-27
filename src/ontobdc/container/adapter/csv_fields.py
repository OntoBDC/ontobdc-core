import csv
from typing import ClassVar


class CsvFields:
    """
    How large a field of a CSV data source may be. A field can hold a long list (the hash of each message of a
    conversation, the ids of related entities), and the module's default of 128 KiB stops reading the whole file at the
    first one that is larger.
    """

    LIMIT: ClassVar[int] = 1 << 30

    @classmethod
    def allow_large(cls) -> None:
        csv.field_size_limit(cls.LIMIT)
