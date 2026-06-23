from typing import List, Tuple, Dict
from ontobdc.shared.adapter.plugin import CheckLoader
from ontobdc.shared.adapter.util import CapturingPrintLog
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ExceptionCommandResponse, EnableCommandResponse


class CheckFixCommand(CliCommandPort):
    """
    Command for executing all hotfixes from all modules.
    """
    METADATA = CliCommandMetadata(
        id="fix",
        logical_component="check",
        description="Execute all hotfixes from all modules.",
        arguments=[
            {
                "accepts": [
                    "--fix",
                ],
                "description": "Execute all hotfixes from all modules.",
                "usage": "ontobdc check --fix",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        return len(args) > 1 and args[0] == 'check'

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return len(self._request.command_args) >= 1 and self._request.command_args[0] == "--fix"

    def _extract_module_from_check_name(self, check_module_name: str) -> str:
        """Extract module name from check module path (e.g., 'ontobdc.storage.plugin.check...' -> 'storage')."""
        parts = check_module_name.split('.')
        if len(parts) >= 2 and parts[0] == 'ontobdc':
            return parts[1]
        return 'unknown'

    def run(self) -> CommandResponse:
        """
        Execute all hotfixes from all modules.
        """
        if self._print_log:
            self._print_log("INFO", "Check Fix", "Executing hotfixes for all modules")

        loader = CheckLoader()
        all_checks: List[Tuple[object, object]] = loader.get_all("check")

        if not all_checks:
            if self._print_log:
                self._print_log("WARN", "Check Fix", "No checks/hotfixes found in any module")
            return EnableCommandResponse(
                title="No Hotfixes Found",
                description="No hotfixes found in any module.",
                content={},
                success=True
            )

        # Group checks/hotfixes by module
        checks_by_module: Dict[str, List[Tuple[object, object]]] = {}

        for check_module, hotfix_module in all_checks:
            module_id = self._extract_module_from_check_name(getattr(check_module, "__name__", ""))
            if module_id not in checks_by_module:
                checks_by_module[module_id] = []
            checks_by_module[module_id].append((check_module, hotfix_module))

        if self._print_log:
            self._print_log("INFO", "Check Fix", f"Found checks/hotfixes in modules: {list(checks_by_module.keys())}")

        # Execute hotfixes for each module
        module_results = []
        overall_has_failures = False

        for module_id, module_checks in sorted(checks_by_module.items()):
            if self._print_log:
                self._print_log("INFO", "Check Fix", f"Processing module: {module_id}")

            results = []
            has_failures = False

            for check_module, hotfix_module in module_checks:
                check_name = getattr(check_module, "__name__", "Unknown Check").split('.')[-2]

                if hotfix_module is None:
                    if self._print_log:
                        self._print_log("INFO", "Check Fix", f"[{module_id}] No hotfix found for {check_name}")
                    results.append({
                        "check": check_name,
                        "hotfix": False,
                        "message": "No hotfix available"
                    })
                    continue

                if self._print_log:
                    self._print_log("INFO", "Check Fix", f"[{module_id}] Running hotfix for {check_name}")

                try:
                    if hasattr(hotfix_module, "main"):
                        exit_code = hotfix_module.main(self._print_log)
                        success = exit_code == 0

                        if not success:
                            has_failures = True
                            overall_has_failures = True

                        results.append({
                            "check": check_name,
                            "hotfix": True,
                            "success": success,
                            "exit_code": exit_code
                        })

                        if self._print_log:
                            status = "APPLIED SUCCESSFULLY" if success else "FAILED TO APPLY"
                            self._print_log("INFO", "Check Fix", f"[{module_id}] Hotfix for {check_name}: {status}")
                except Exception as e:
                    has_failures = True
                    overall_has_failures = True
                    results.append({
                        "check": check_name,
                        "hotfix": True,
                        "success": False,
                        "error": str(e)
                    })
                    if self._print_log:
                        self._print_log("ERROR", "Check Fix", f"[{module_id}] Hotfix for {check_name} raised exception: {str(e)}")

            module_results.append({
                "module": module_id,
                "hotfixes_run": len([r for r in results if r["hotfix"]]),
                "has_failures": has_failures,
                "results": results
            })

        # Summary
        summary = {
            "modules_processed": len(module_results),
            "total_hotfixes_run": sum(m["hotfixes_run"] for m in module_results),
            "modules_with_failures": [m["module"] for m in module_results if m["has_failures"]],
            "module_results": module_results
        }

        if overall_has_failures:
            return ExceptionCommandResponse(
                title="Some Hotfixes Failed",
                description="One or more hotfixes failed across modules.",
                content=summary
            )

        return EnableCommandResponse(
            title="All Hotfixes Applied",
            description="All available hotfixes applied successfully.",
            content=summary,
            success=True
        )
