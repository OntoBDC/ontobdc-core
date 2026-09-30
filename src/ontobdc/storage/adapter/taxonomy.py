from typing import ClassVar


class OpenFileMetadataTaxonomy:
    STATE_NAME: ClassVar[str] = "file_metadata_extracted"
    EVENT_FILE_NAME: ClassVar[str] = f"__{STATE_NAME}__.json"
    MODULE_NAME: ClassVar[str] = "storage"
    PHASE_NAME: ClassVar[str] = "open_file"
    ENTITY_NAME: ClassVar[str] = "file"
    RESOLVED_PATH_KEY: ClassVar[str] = "resolved_path"
