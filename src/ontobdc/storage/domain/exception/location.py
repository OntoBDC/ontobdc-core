from pathlib import Path


class InconsistentStorageIndexError(ValueError):
    """
    Raised when a storage index records a location outside the storage root it
    belongs to: every container lives under its root, so such an index is
    inconsistent and cannot be read for the root's current place.
    """

    def __init__(self, location: Path, recorded_root: Path) -> None:
        self.location: Path = location
        self.recorded_root: Path = recorded_root
        super().__init__(
            f"The storage index records {location} outside its storage root "
            f"{recorded_root}."
        )
