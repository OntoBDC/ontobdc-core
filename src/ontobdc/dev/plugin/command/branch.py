import os
import subprocess
from typing import List, Dict, Any, Optional

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.shared.adapter.config import ConfigDataAdapter


class DevBranchCommand(CliCommandPort):
    """
    Command for managing git branches across repositories (status mode).
    """
    METADATA = CliCommandMetadata(
        id="branch",
        logical_component="dev",
        description="List modified files and branches for all repositories.",
        arguments=[
            {
                "accepts": ["branch"],
                "description": "List modified files and branches for all repositories.",
                "usage": "ontobdc dev branch",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "dev":
            return False
        return len(args) == 2 and args[1] == "branch"

    def __init__(self, request: CliCommandRequest):
        self._request = request
        self._print_log = None
        self._root_dir = ConfigDataAdapter().root_dir
        self._submodules = ["ontobdc-wip", "ontobdc-core", "core", "wip"]

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        args = self._request.command_args
        return len(args) == 1 and args[0] == "branch"

    def run(self) -> CommandResponse:
        repos = self._get_repos()
        
        results = []
        for repo_path in repos:
            if not os.path.exists(repo_path):
                continue
            
            if not os.path.isdir(os.path.join(repo_path, ".git")) and not os.path.isfile(os.path.join(repo_path, ".git")):
                continue
                
            repo_name = os.path.basename(repo_path)
            status_info = self._repo_status(repo_path, repo_name)
            if status_info:
                results.append(status_info)

        return CommandResponse(
            title="Branch Command",
            description="Executed branch status across repositories.",
            content={"repositories": results}
        )

    def _get_repos(self) -> List[str]:
        repos = []
        
        gitmodules_path = os.path.join(self._root_dir, ".gitmodules")
        if os.path.exists(gitmodules_path):
            try:
                with open(gitmodules_path, "r") as f:
                    for line in f:
                        if "path =" in line:
                            path = line.split("=")[1].strip()
                            repos.append(os.path.join(self._root_dir, path))
            except Exception:
                pass
                
        for sub in self._submodules:
            sub_path = os.path.join(self._root_dir, sub)
            if sub_path not in repos and os.path.exists(sub_path):
                repos.append(sub_path)
                
        if self._root_dir not in repos:
            repos.append(self._root_dir)
            
        return repos

    def _run_git(self, cwd: str, cmd: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def _run_git_status(self, cwd: str) -> str:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return result.stdout
        except Exception:
            return ""

    def _repo_status(self, repo_path: str, repo_name: str) -> Optional[Dict[str, Any]]:
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            return None
            
        branch = self._run_git(repo_path, ["branch", "--show-current"])
        if not branch:
            branch = self._run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
            if not branch:
                branch = "unknown"

        status_out = self._run_git_status(repo_path)
        
        files = []
        for line in status_out.splitlines():
            if not line:
                continue
            code = line[:2]
            path = line[3:]
            
            if repo_path == self._root_dir and path in self._submodules:
                continue
                
            state = "modified"
            if "??" in code:
                state = "untracked"
            elif "A" in code:
                state = "added"
            elif "M" in code:
                state = "modified"
            elif "D" in code:
                state = "deleted"
                
            files.append({"file": path, "state": state})
            
        print(f"")
        print(f"\033[33m❯ \033[37m{repo_name} \033[36m({branch})\033[0m")
        if not files:
            print("  \033[90m• clean\033[0m")
        else:
            for f in files:
                color = "\033[37m"
                if f["state"] == "untracked":
                    color = "\033[36m"
                elif f["state"] == "added":
                    color = "\033[32m"
                elif f["state"] == "modified":
                    color = "\033[33m"
                elif f["state"] == "deleted":
                    color = "\033[31m"
                print(f"  {color}[{f['state']}]\033[0m \033[90m{f['file']}\033[0m")

        return {
            "repository": repo_name,
            "branch": branch,
            "files": files
        }
