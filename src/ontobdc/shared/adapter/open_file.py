from typing import Any, Dict

from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport


OPEN_FILE_INPUT_SCHEMA: Dict[str, Any] = {
    "properties": {
        OpenFileChainSupport.PATH_KEY: {"type": "string"},
        OpenFileChainSupport.KIND_KEY: {"type": "string", "required": True},
        OpenFileChainSupport.NAME_KEY: {"type": "string", "required": True},
        OpenFileChainSupport.DATA_KEY: {"type": "object"},
        OpenFileChainSupport.LANGUAGE_KEY: {"type": "string"},
    },
}

OPEN_FILE_OUTPUT_SCHEMA: Dict[str, Any] = {
    "properties": {
        "handled": {"type": "boolean"},
        "handler": {"type": "string"},
        "message": {"type": "string"},
        "error": {"type": "string"},
    },
}
