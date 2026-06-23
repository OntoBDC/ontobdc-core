import os
import subprocess
from typing import List

from ontobdc.cli.domain.port.command import CliCommandMetadata
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.dev.plugin.command.branch import DevBranchCommand


class DevBranchChangelogCommand(DevBranchCommand):
    """
    Command for generating a changelog across all repositories.
    """
    METADATA = CliCommandMetadata(
        id="branch-changelog",
        logical_component="dev",
        description="Generate changelog across all repositories.",
        arguments=[
            {
                "accepts": ["--changelog"],
                "description": "Generate changelog across all repositories.",
                "usage": "ontobdc dev branch --changelog [target_ref]",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "dev":
            return False
        return len(args) >= 3 and args[1] == "branch" and args[2] == "--changelog"

    def check(self) -> bool:
        args = self._request.command_args
        return len(args) in [2, 3] and args[0] == "branch" and args[1] == "--changelog"

    def run(self) -> CommandResponse:
        args = self._request.command_args
        target_ref = args[2] if len(args) > 2 else None
        
        repos = self._get_repos()
        
        results = []
        for repo_path in repos:
            if not os.path.exists(repo_path):
                continue
            
            if not os.path.isdir(os.path.join(repo_path, ".git")) and not os.path.isfile(os.path.join(repo_path, ".git")):
                continue
                
            repo_name = os.path.basename(repo_path)
            res = self._git_branch_changelog(repo_path, repo_name, target_ref)
            if res:
                results.append(res)

        return CommandResponse(
            title="Branch Changelog Command",
            description="Executed branch changelog across repositories.",
            content={"repositories": results}
        )

    def _git_branch_changelog(self, repo_path: str, repo_name: str, target_ref: str) -> dict:
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            return {}
            
        print("")
        print(f"\033[33m❯ \033[37mProcessing \033[36m{repo_name}\033[0m")
        
        result_info = {"repository": repo_name}
        
        print(f"  \033[90mChangelog feature not fully ported yet for {repo_name}\033[0m")
        result_info["status"] = "skipped"
            
        return result_info
