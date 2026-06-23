from typing import List, Tuple
from ontobdc.shared.adapter.plugin import CheckLoader
from ontobdc.shared.adapter.util import CapturingPrintLog
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ExceptionCommandResponse, EnableCommandResponse

class CheckModuleCommand(CliCommandPort):
    """
    Command for executing all checks from a specific module.
    """
    METADATA = CliCommandMetadata(
        id="module",
        logical_component="check",
        description="Execute all checks from a specific module.",
        arguments=[
            {
                "accepts": [
                    "--module",
                ],
                "description": "Execute all checks from a specific module.",
                "usage": "ontobdc check --module <module_id>",
            },
        ],
    )

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
        return len(self._request.command_args) >= 2 and self._request.command_args[0] == "--module"

    def run(self) -> CommandResponse:
        """
        Execute all checks from the specified module.
        """
        module_id = self._request.command_args[1]

        if self._print_log:
            self._print_log("INFO", "Check Module", f"Executing checks for module: {module_id}")

        loader = CheckLoader()
        all_checks: List[Tuple[object, object]] = loader.get_all("check")

        # Filter checks by module
        module_prefix = f"ontobdc.{module_id}.plugin.check"
        module_checks = [
            (c, h) for c, h in all_checks
            if getattr(c, "__name__", "").startswith(module_prefix)
        ]

        if not module_checks:
            if self._print_log:
                self._print_log("WARN", "Check Module", f"No checks found for module: {module_id}")
            return ExceptionCommandResponse(
                title="No Checks Found",
                description=f"No checks found for module: {module_id}",
                content={}
            )

        results = []
        has_failures = False

        for check_module, hotfix_module in module_checks:
            check_name = getattr(check_module, "__name__", "Unknown Check").split('.')[-2]

            if self._print_log:
                self._print_log("INFO", "Check Module", f"Running check: {check_name}")

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
                        self._print_log("INFO", "Check Module", f"Check {check_name}: {status}")
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
                    self._print_log("ERROR", "Check Module", f"Check {check_name} raised exception: {str(e)}")

        if has_failures:
            return ExceptionCommandResponse(
                title="Module Checks Failed",
                description=f"One or more checks failed for module: {module_id}",
                content={"results": results}
            )

        return EnableCommandResponse(
            title="Module Checks Passed",
            description=f"All checks passed successfully for module: {module_id}",
            content={"results": results},
            success=True
        )
