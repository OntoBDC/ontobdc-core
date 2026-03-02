
import os
import zipfile
from typing import List, Optional
from ontobdc.module.resource.domain.port.repository import FileRepositoryPort


class ZipArchiveAdapter:
    """
    Adapter for handling zip archives.
    """
    def __init__(self, repository: FileRepositoryPort, file_path: str, encoding: str = "utf-8"):
        self.repository: FileRepositoryPort = repository
        self.file_path: str = file_path
        self.encoding: str = encoding

    def extract(self) -> List[str]:
        """
        Unzips the file to the same directory where the zip file is located.
        Returns a list of absolute paths of the extracted files.
        """
        # Ensure we have an absolute path for the target directory
        # If file_path is from repository, it should be absolute or resolvable.
        # Since we want to extract to "the same folder", we assume file_path provides that context.
        
        # We use repository to open the zip stream to respect read abstractions,
        # but we must use filesystem operations to write (extract) the files.
        
        # Extract to a subdirectory named after the zip file (without extension)
        zip_filename = os.path.basename(self.file_path)
        folder_name = os.path.splitext(zip_filename)[0]
        target_dir = os.path.join(os.path.dirname(self.file_path), folder_name)
        
        # Create target directory if it doesn't exist
        # We assume filesystem access here as ZipFile.extractall writes to disk.
        os.makedirs(target_dir, exist_ok=True)
        
        extracted_files = []
        
        # Open zip via repository
        f = self.repository.open_file(self.file_path, "rb")
        if not f:
            return []
            
        with f:
            try:
                with zipfile.ZipFile(f) as z:
                    # Extract all files
                    z.extractall(path=target_dir)
                    
                    # Collect extracted file paths
                    for name in z.namelist():
                        extracted_files.append(os.path.join(target_dir, name))
            except zipfile.BadZipFile:
                return []
                
        return extracted_files


