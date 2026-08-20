from typing import Optional

from ontobdc.view.plugin.check.work_stream_script_common import script_is_fresh


def main(surface_path: Optional[str] = None) -> int:
    return 0 if script_is_fresh(surface_path, "dimension_card") else 1
