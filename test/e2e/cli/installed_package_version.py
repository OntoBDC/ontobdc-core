import json
import subprocess
import sys
from typing import Any, Dict, List


class InstalledPackageVersionLookup:
    """
    Resolves a package's installed version the way `pip list` reports it,
    using `sys.executable` -- the same venv interpreter
    `OntobdcCliProcessRunner` resolves its `ontobdc` executable from, never
    whatever `ontobdc`/`pip` happen to resolve to on PATH.
    """
    _TIMEOUT_SECONDS: int = 30

    def version_of(self, package_name: str) -> str:
        """
        Return the version `pip list` reports for *package_name*.
        """
        completed_process: "subprocess.CompletedProcess[str]" = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=self._TIMEOUT_SECONDS,
            check=True,
        )

        installed_packages: List[Dict[str, Any]] = json.loads(completed_process.stdout)
        for installed_package in installed_packages:
            if installed_package["name"].lower() == package_name.lower():
                return installed_package["version"]

        raise LookupError(
            f"Package '{package_name}' was not found in `pip list` output "
            f"for interpreter '{sys.executable}'."
        )
