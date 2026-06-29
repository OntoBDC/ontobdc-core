
from typing import List, Tuple
from ontobdc.shared.adapter.plugin import CheckLoader
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse, EnableCommandResponse


class StorageHotfixCommand(CliCommandPort):
    """
    Command for executing all storage hotfixes.
    """
    METADATA = CliCommandMetadata(
        id="fix",
        logical_component="storage",
        description="Execute all storage hotfixes.",
        arguments=[
            {
                "accepts": [
                    "--fix",
                ],
                "description": "Execute all hotfixes to repair the storage component.",
                "usage": "ontobdc storage --fix",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage hotfix command at the CLI routing stage.
        """
        return len(args) > 1 and args[0] == "storage" and args[1] == "--fix"

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
        return len(self._request.command_args) == 1 and self._request.command_args[0] == "--fix"

    def run(self) -> CommandResponse:
        """
        Execute all storage hotfixes.
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
                if hotfix_module and hasattr(hotfix_module, "main"):
                    exit_code = hotfix_module.main(self._print_log)
                    success = exit_code == 0
                    
                    if not success:
                        has_failures = True
                    
                    results.append({
                        "hotfix": check_name,
                        "success": success,
                        "exit_code": exit_code
                    })
            except Exception as e:
                has_failures = True
                results.append({
                    "hotfix": check_name,
                    "success": False,
                    "error": str(e)
                })

        if has_failures:
            return ExceptionCommandResponse(
                title="Storage Hotfixes Failed",
                description="One or more storage hotfixes failed.",
                content={"results": results}
            )

        return EnableCommandResponse(
            title="Storage Hotfixes Passed",
            description="All storage hotfixes executed successfully.",
            content={"results": results},
            success=True
        )
