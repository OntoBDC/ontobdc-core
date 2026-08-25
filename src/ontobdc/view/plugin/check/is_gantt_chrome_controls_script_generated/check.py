from typing import Optional

from ontobdc.view.plugin.check.gantt_script_common import script_is_fresh


def main(surface_path: Optional[str] = None) -> int:
    return 0 if script_is_fresh(surface_path, "chrome_controls") else 1
