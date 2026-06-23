import os
import subprocess
from typing import List, Dict, Any, Optional

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.shared.adapter.config import ConfigDataAdapter


class DevCommitCommand(CliCommandPort):
    """
    Command for committing and pushing changes across repositories.
    """
    METADATA = CliCommandMetadata(
        id="commit",
        logical_component="dev",
        description="Commit and push changes across all repositories.",
        arguments=[
            {
                "accepts": ["commit"],
                "description": "Commit and push changes with a message.",
                "usage": "ontobdc dev commit \"<message>\"",
                "valued": True,
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "dev":
            return False
        return len(args) >= 2 and args[1] == "commit"

    def __init__(self, request: CliCommandRequest):
        self._request = request
        self._print_log = None
        self._root_dir = ConfigDataAdapter().root_dir
        self._submodules = ["ontobdc-wip", "ontobdc-core", "core", "wip"]

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        args = self._request.command_args
        return len(args) == 2 and args[0] == "commit"

    def run(self) -> CommandResponse:
        message = self._request.command_args[1]
        
        repos = self._get_repos()
        
        print(f"\n\033[36mStarting commit process...\033[0m")
        print(f"\033[90mRoot Directory: {self._root_dir}\033[0m")
        print(f"\033[90mMessage: \033[37m\"{message}\"\033[0m\n")

        results = []
        for repo_path in repos:
            if not os.path.exists(repo_path):
                continue
            
            if not os.path.isdir(os.path.join(repo_path, ".git")) and not os.path.isfile(os.path.join(repo_path, ".git")):
                continue
                
            repo_name = os.path.basename(repo_path)
            res = self._git_commit(repo_path, repo_name, message)
            if res:
                results.append(res)

        print(f"\n\033[32mSuccess! Commit finished.\033[0m\n")

        return CommandResponse(
            title="Commit Command",
            description=f"Executed commit across repositories with message: '{message}'.",
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

    def _git_commit(self, repo_path: str, repo_name: str, message: str) -> dict:
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            return {}
            
        branch = self._run_git(repo_path, ["branch", "--show-current"])
        if not branch:
            branch = self._run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
            if not branch:
                branch = "unknown"

        print(f"\n\033[37m❯ Processing {repo_name} \033[36m({branch})\033[0m")
        
        result_info = {"repository": repo_name, "branch": branch, "status": "unknown"}
        
        # 1. Add all changes
        try:
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
            print("   \033[32m• Added all changes\033[0m")
        except subprocess.CalledProcessError:
            print("   \033[31m• Failed to add changes\033[0m")
            result_info["status"] = "add_error"
            return result_info

        # 2. Check for changes
        has_changes = subprocess.run(["git", "diff-index", "--quiet", "HEAD", "--"], cwd=repo_path).returncode != 0
        
        if has_changes:
            # 3. Commit changes
            try:
                subprocess.run(["git", "commit", "-m", message], cwd=repo_path, capture_output=True, check=True)
                print("   \033[32m• Committed changes\033[0m")
                result_info["status"] = "committed"
            except subprocess.CalledProcessError:
                print("   \033[31m• Failed to commit changes\033[0m")
                result_info["status"] = "commit_error"
                return result_info

            # 4. Push if remote exists
            remote = self._run_git(repo_path, ["remote"])
            if remote:
                push_cmd = ["git", "push"]
                try:
                    subprocess.run(push_cmd, cwd=repo_path, capture_output=True, check=True)
                    print("   \033[32m• Pushed to remote\033[0m")
                    result_info["pushed"] = True
                except subprocess.CalledProcessError:
                    # Try setting upstream
                    try:
                        subprocess.run(push_cmd + ["--set-upstream", "origin", branch], cwd=repo_path, capture_output=True, check=True)
                        print("   \033[32m• Pushed to remote (set upstream)\033[0m")
                        result_info["pushed"] = True
                    except subprocess.CalledProcessError:
                        print("   \033[31m✗ Push failed\033[0m")
                        result_info["pushed"] = False
            else:
                print("   \033[90m• No remote repository found (skipping push)\033[0m")
                result_info["pushed"] = False
        else:
            print("   \033[90m• No changes to commit\033[0m")
            result_info["status"] = "no_changes"

        return result_info
