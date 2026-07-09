import os
import subprocess
from typing import List

from ontobdc.cli.domain.port.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.dev.plugin.command.branch import DevBranchCommand


class DevBranchCheckoutCommand(DevBranchCommand):
    """
    Command for checking out a git branch across all repositories.
    """
    METADATA = CliCommandMetadata(
        id="branch-checkout",
        logical_component="dev",
        description="Checkout a branch across all repositories.",
        arguments=[
            {
                "accepts": ["--checkout"],
                "description": "Checkout a branch across all repositories.",
                "usage": "ontobdc dev branch --checkout <branch_name>",
                "valued": True,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "dev":
            return False
        return len(args) == 4 and args[1] == "branch" and args[2] == "--checkout"

    def check(self) -> bool:
        args = self._request.command_args
        return len(args) == 3 and args[0] == "branch" and args[1] == "--checkout"

    def run(self) -> CommandResponse:
        branch_name = self._request.command_args[2]
        repos = self._get_repos()
        
        results = []
        for repo_path in repos:
            if not os.path.exists(repo_path):
                continue
            
            if not os.path.isdir(os.path.join(repo_path, ".git")) and not os.path.isfile(os.path.join(repo_path, ".git")):
                continue
                
            repo_name = os.path.basename(repo_path)
            res = self._git_branch_checkout(repo_path, repo_name, branch_name)
            if res:
                results.append(res)

        return CommandResponse(
            title="Branch Checkout Command",
            description=f"Executed branch checkout '{branch_name}' across repositories.",
            content={"repositories": results}
        )

    def _git_branch_checkout(self, repo_path: str, repo_name: str, branch_name: str) -> dict:
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            return {}
            
        print("")
        print(f"\033[33m❯ \033[37mProcessing \033[36m{repo_name}\033[0m")
        
        result_info = {"repository": repo_name}
        
        has_local = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_path).returncode == 0
        has_remote = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch_name}"], cwd=repo_path).returncode == 0
        
        if has_local or has_remote:
            try:
                subprocess.run(["git", "checkout", branch_name], cwd=repo_path, capture_output=True, text=True, check=True)
                print(f"  \033[32m✓ Checked out\033[0m")
                result_info["status"] = "checked_out"
            except subprocess.CalledProcessError:
                print(f"  \033[31m✗ Checkout failed\033[0m")
                result_info["status"] = "error"
        else:
            print(f"  \033[33m! Warning: Branch '{branch_name}' does not exist in this repo\033[0m")
            result_info["status"] = "not_found"
                
        return result_info
