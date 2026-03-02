
import os
import stat
import tempfile
import shutil
from typing import Any, Dict
from ontobdc.core.domain.port.verification import VerificationStrategyPort


class HasReadPermission(VerificationStrategyPort):
    def verify(self, input_key: str, input_value: Any, inputs: Dict[str, Any]) -> bool:
        """
        Checks if the repository has read permissions.
        Assumes input_value is a RepositoryPort with path_folders or a path string.
        """
        paths = self._get_paths(input_value)
        if not paths:
            # If no paths found, assume invalid or not applicable, return False for safety
            return False
            
        for path in paths:
            if not os.path.exists(path) or not os.access(path, os.R_OK):
                return False
        return True

    def _get_paths(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        
        # Check for DocumentRepositoryPort interface
        if hasattr(value, "path_folders"):
            folders = value.path_folders
            paths = []
            for folder in folders:
                if hasattr(folder, "path"):
                    paths.append(str(folder.path))
            return paths
            
        # Fallback for simple objects with path attribute
        if hasattr(value, "path"):
            return [str(value.path)]
            
        return []


class HasWritePermission(VerificationStrategyPort):
    def verify(self, input_key: str, input_value: Any, inputs: Dict[str, Any]) -> bool:
        """
        Checks if the repository has write permissions.
        Assumes input_value is a RepositoryPort with path_folders or a path string.
        """
        paths = self._get_paths(input_value)
        if not paths:
            return False
            
        for path in paths:
            if not os.path.exists(path) or not os.access(path, os.W_OK):
                return False
        return True

    def _get_paths(self, value: Any) -> list[str]:
        # Reuse logic or duplicate for independence. Duplicating for simplicity here.
        if isinstance(value, str):
            return [value]
        
        if hasattr(value, "path_folders"):
            folders = value.path_folders
            paths = []
            for folder in folders:
                if hasattr(folder, "path"):
                    paths.append(str(folder.path))
            return paths
            
        if hasattr(value, "path"):
            return [str(value.path)]
            
        return []


if __name__ == "__main__":
    # Simple test suite
    print("Running verification strategy tests...")
    
    # Setup
    temp_dir = tempfile.mkdtemp()
    print(f"Created temp dir: {temp_dir}")
    
    try:
        # Mock Repository
        class MockFolder:
            def __init__(self, path):
                self.path = path
        
        class MockRepository:
            def __init__(self, path):
                self.path_folders = [MockFolder(path)]

        repo = MockRepository(temp_dir)
        
        # Test Read Permission
        read_verifier = HasReadPermission()
        is_readable = read_verifier.verify("repo", repo, {})
        print(f"Read Permission (Expected True): {is_readable}")
        assert is_readable is True
        
        # Test Write Permission
        write_verifier = HasWritePermission()
        is_writable = write_verifier.verify("repo", repo, {})
        print(f"Write Permission (Expected True): {is_writable}")
        assert is_writable is True
        
        # Modify permissions to Read-Only
        os.chmod(temp_dir, stat.S_IREAD | stat.S_IXUSR) # Read and Execute (to traverse) only
        
        # Test Write Permission again
        is_writable_now = write_verifier.verify("repo", repo, {})
        print(f"Write Permission (Expected False): {is_writable_now}")
        
        # Note: Running as root/superuser might bypass permission checks, but standard user should fail
        if os.geteuid() != 0:
            assert is_writable_now is False
        else:
            print("Skipping False assertion for Write Permission (running as root)")

    finally:
        # Cleanup
        # Restore permissions to allow deletion
        os.chmod(temp_dir, stat.S_IRWXU)
        shutil.rmtree(temp_dir)
        print("Cleanup done.")
