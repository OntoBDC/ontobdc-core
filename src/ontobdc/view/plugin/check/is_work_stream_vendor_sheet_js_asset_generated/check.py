from typing import Optional

from ontobdc.view.plugin.check.work_stream_script_common import script_is_fresh

VENDOR_SHEET_JS_NAME: str = "xlsx-0.18.5.full.min"


def main(surface_path: Optional[str] = None) -> int:
    return 0 if script_is_fresh(surface_path, VENDOR_SHEET_JS_NAME) else 1
