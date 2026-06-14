
from typing import List, Tuple
from ontobdc.shared.adapter.plugin import CheckLoader
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ExceptionCommandResponse, EnableCommandResponse


class StorageCheckCommand(CliCommandPort):
    """
    Command for executing all storage checks.
    """
    METADATA = CliCommandMetadata(
        id="check",
        logical_component="storage",
        description="Execute all storage checks.",
        arguments=[
            {
                "accepts": [
                    "--check",
                ],
                "description": "Execute all checks to verify the health of the storage component.",
                "usage": "ontobdc storage --check",
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
        # For check command, we usually want it to run even if not enabled? 
        # Actually, usually checks are run to see if it's healthy. Let's see what user wants.
        # Most commands use `is_enabled()`. I'll use it, or maybe it doesn't matter if there's no args other than --check.
        return len(self._request.command_args) == 1 and self._request.command_args[0] == "--check"

    def run(self) -> CommandResponse:
        """
        Execute all storage checks.
        """
        loader = CheckLoader()
        all_checks: List[Tuple[object, object]] = loader.get_all("check")
        
        # Filter only storage checks
        storage_checks = [
            (c, h) for c, h in all_checks
            if getattr(c, "__name__", "").startswith("ontobdc.storage.plugin.check")
        ]
        
        results = []
        has_failures = False

        for check_module, hotfix_module in storage_checks:
            check_name = getattr(check_module, "__name__", "Unknown Check").split('.')[-2]
            
            try:
                if hasattr(check_module, "main"):
                    exit_code = check_module.main(self._print_log)
                    success = exit_code == 0
                    
                    if not success:
                        has_failures = True
                    
                    results.append({
                        "check": check_name,
                        "success": success,
                        "exit_code": exit_code
                    })
            except Exception as e:
                has_failures = True
                results.append({
                    "check": check_name,
                    "success": False,
                    "error": str(e)
                })

        if has_failures:
            return ExceptionCommandResponse(
                title="Storage Checks Failed",
                description="One or more storage checks failed.",
                content={"results": results}
            )

        return EnableCommandResponse(
            title="Storage Checks Passed",
            description="All storage checks passed successfully.",
            content={"results": results},
            success=True
        )
