
from abc import ABC


class FilesystemPort(ABC):
    pass


class FolderPort(ABC):
    RUNTIME_FIELDS = {"path", "segment_separator", "filesystem"}
    ADAPTERS = {
        "local": "ontobdc.resource.src.domain.adapter.folder.LocalFolderAdapter",
    }


class MediaTypePort(ABC):
    pass
