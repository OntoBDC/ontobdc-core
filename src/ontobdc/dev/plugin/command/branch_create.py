import os
import subprocess
from typing import List

from ontobdc.cli.domain.port.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.dev.plugin.command.branch import DevBranchCommand


class DevBranchCreateCommand(DevBranchCommand):
    """
    Command for creating a git branch across all repositories.
    """
    METADATA = CliCommandMetadata(
        id="branch-create",
        logical_component="dev",
        description="Create a branch across all repositories.",
        arguments=[
            {
                "accepts": ["--create"],
                "description": "Create a branch across all repositories.",
                "usage": "ontobdc dev branch --create <branch_name>",
                "valued": True,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "dev":
            return False
        return len(args) == 4 and args[1] == "branch" and args[2] == "--create"

    def check(self) -> bool:
        args = self._request.command_args
        return len(args) == 3 and args[0] == "branch" and args[1] == "--create"

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
            res = self._git_branch_create(repo_path, repo_name, branch_name)
            if res:
                results.append(res)

        return CommandResponse(
            title="Branch Create Command",
            description=f"Executed branch create '{branch_name}' across repositories.",
            content={"repositories": results}
        )

    def _git_branch_create(self, repo_path: str, repo_name: str, branch_name: str) -> dict:
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            return {}
            
        print("")
        print(f"\033[33m❯ \033[37mProcessing \033[36m{repo_name}\033[0m")
        
        result_info = {"repository": repo_name}
        
        if self._run_git(repo_path, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"]):
            print(f"  \033[33m! Branch '{branch_name}' already exists\033[0m")
            result_info["status"] = "exists"
        else:
            try:
                subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, capture_output=True, check=True)
                print(f"  \033[32m✓ Created local branch\033[0m")
                result_info["status"] = "created"
                
                remote = self._run_git(repo_path, ["remote"])
                if remote:
                    try:
                        subprocess.run(["git", "push", "--set-upstream", "origin", branch_name], cwd=repo_path, capture_output=True, check=True)
                        print(f"  \033[32m✓ Pushed upstream\033[0m")
                        result_info["pushed"] = True
                    except subprocess.CalledProcessError:
                        print(f"  \033[31m✗ Failed to push upstream\033[0m")
                        result_info["pushed"] = False
            except subprocess.CalledProcessError:
                print(f"  \033[31m✗ Failed to create branch\033[0m")
                result_info["status"] = "error"
                
        return result_info
