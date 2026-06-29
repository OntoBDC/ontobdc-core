
from typing import List, Tuple, Dict
from ontobdc.shared.adapter.plugin import CheckLoader
from ontobdc.shared.adapter.util import CapturingPrintLog
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse, CheckFailCommandResponse, EnableCommandResponse


class CheckBaseCommand(CliCommandPort):
    """
    Base command for check plugin
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="check",
        description="Execute all checks from all modules.",
        arguments=[
            {
                "accepts": [
                    "--all",
                ],
                "description": "Execute all checks from all modules.",
                "usage": "ontobdc check --all",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        return len(args) >= 1 and args[0] == 'check'

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return len(self._request.command_args) == 0 or self._request.command_args[0] == "--all"

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if self._print_log:
            self._print_log("INFO", "Check All", "Executing checks for all modules")

        loader = CheckLoader(self._print_log)
        all_checks: List[Tuple[object, object]] = loader.get_all("check")

        if not all_checks:
            if self._print_log:
                self._print_log("WARN", "Check All", "No checks found in any module")
            return ExceptionCommandResponse(
                title="No Checks Found",
                description="No checks found in any module",
                content={}
            )

        # Group checks by module
        checks_by_module: Dict[str, List[Tuple[object, object]]] = {}
        # modules_without_checks: Set[str] = set()

        for check_module, hotfix_module in all_checks:
            module_id = self._extract_module_from_check_name(getattr(check_module, "__name__", ""))
            if module_id not in checks_by_module:
                checks_by_module[module_id] = []
            checks_by_module[module_id].append((check_module, hotfix_module))

        if self._print_log:
            self._print_log("INFO", "Check All", f"Found checks in modules: {list(checks_by_module.keys())}")

        # Execute checks for each module
        module_results = []
        overall_has_failures = False

        for module_id, module_checks in sorted(checks_by_module.items()):
            if self._print_log:
                self._print_log("INFO", "Check All", f"Processing module: {module_id} ({len(module_checks)} checks)")

            module_result = self._run_checks_for_module(module_id, module_checks)
            module_results.append(module_result)

            if module_result["has_failures"]:
                overall_has_failures = True

        # Check for modules that don't have any checks
        # This requires knowing what modules exist - we'll discover them from the filesystem
        if self._print_log:
            self._print_log("INFO", "Check All", "Checking for modules without checks")

        # Summary
        summary = {
            "modules_checked": len(module_results),
            "total_checks_run": sum(m["checks_run"] for m in module_results),
            "modules_with_failures": [m["module"] for m in module_results if m["has_failures"]],
            "module_results": module_results
        }

        if overall_has_failures:
            return CheckFailCommandResponse(
                title="All Module Checks Failed",
                description="One or more checks failed across modules",
                content=summary
            )

        return EnableCommandResponse(
            title="All Module Checks Passed",
            description="All checks passed successfully across all modules",
            content=summary,
            success=True
        )

    def _extract_module_from_check_name(self, check_module_name: str) -> str:
        """Extract module name from check module path (e.g., 'ontobdc.storage.plugin.check...' -> 'storage')."""
        parts = check_module_name.split('.')
        if len(parts) >= 2 and parts[0] == 'ontobdc':
            return parts[1]

        return 'unknown'

    def _run_checks_for_module(self, module_id: str, check_modules: List[Tuple[object, object]]) -> Dict:
        """Run all checks for a specific module and return results."""
        results = []
        has_failures = False
        module_check_count = len(check_modules)

        for check_module, hotfix_module in check_modules:
            check_name = getattr(check_module, "__name__", "Unknown Check").split('.')[-2]

            if self._print_log:
                self._print_log("INFO", "Check All", f"[{module_id}] Running check: {check_name}")

            # Capturar mensagens de erro durante a execução do check
            error_messages = []
            capturing_print_log = CapturingPrintLog(self._print_log, error_messages)

            try:
                if hasattr(check_module, "main"):
                    exit_code = check_module.main(capturing_print_log)
                    success = exit_code == 0

                    if not success:
                        has_failures = True

                    result = {
                        "check": check_name,
                        "success": success,
                        "exit_code": exit_code
                    }

                    # Adicionar mensagens de erro ao resultado se houver falha
                    if error_messages:
                        result["error_details"] = error_messages

                    results.append(result)

                    if self._print_log:
                        status = "PASSED" if success else "FAILED"
                        self._print_log("INFO", "Check All", f"[{module_id}] Check {check_name}: {status}")
            except Exception as e:
                has_failures = True
                result = {
                    "check": check_name,
                    "success": False,
                    "error": str(e)
                }
                if error_messages:
                    result["error_details"] = error_messages
                results.append(result)
                if self._print_log:
                    self._print_log("ERROR", "Check All", f"[{module_id}] Check {check_name} raised exception: {str(e)}")

        return {
            "module": module_id,
            "checks_run": module_check_count,
            "has_failures": has_failures,
            "results": results
        }



