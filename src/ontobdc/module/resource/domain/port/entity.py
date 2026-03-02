
from abc import ABC


class FilesystemPort(ABC):
    pass


class FolderPort(ABC):
    RUNTIME_FIELDS = {"path", "segment_separator", "filesystem"}
    ADAPTERS = {
        "local": "ontobdc.module.resource.adapter.folder.LocalFolderAdapter",
    }


class MediaTypePort(ABC):
    pass
