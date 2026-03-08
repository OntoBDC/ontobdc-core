
import json
import os
from typing import Any, Dict, List, Optional
from datapackage import Package, Resource
from ontobdc.module.resource.domain.port.repository import FileRepositoryPort


class DataPackageAdapter:
    """
    Adapter for handling Frictionless Data Packages.
    """
    
    def __init__(self, repository: FileRepositoryPort, base_path: str):
        self.repository = repository
        self.base_path = base_path.rstrip('/')
        # Store metadata in .__ontobdc__ directory
        self.metadata_dir = f"{self.base_path}/.__ontobdc__"
        self.descriptor_path = f"{self.metadata_dir}/datapackage.json"
        self._package = None

    @property
    def package(self) -> Package:
        if self._package is None:
            self._load_or_create_package()
        return self._package

    def _load_or_create_package(self):
        """Load existing datapackage.json or create a new one."""
        if self.repository.exists(self.descriptor_path):
            # We need to read the content and pass it to Package
            # Package(descriptor) can accept a dict or a path.
            # Since our repository is abstract, we read the content as dict.
            content = self.repository.get_json(self.descriptor_path)
            if content:
                self._package = Package(content)
            else:
                self._package = Package()
        else:
            self._package = Package()

    def read_csv_resource(self, resource_name: str) -> List[Dict[str, Any]]:
        """
        Read a CSV resource from the package.
        """
        resource = self.package.get_resource(resource_name)
        if not resource:
            return []
        
        path = resource.descriptor.get("path")
        if path and resource.descriptor.get("format") == "csv":
            full_path = f"{os.path.dirname(self.descriptor_path)}/{path}"
            
            if self.repository.exists(full_path):
                import csv
                import io
                
                # Read raw content
                # open_file handles utf-8. If BOM exists, utf-8-sig might be needed or manual strip.
                # My open_file uses utf-8. 
                # Let's read and check for BOM manually or assume utf-8-sig logic in open_file?
                # open_file uses 'utf-8'. BOM is \ufeff.
                with self.repository.open_file(full_path, "r") as f:
                    content = f.read()
                
                # Remove BOM if present
                if content.startswith('\ufeff'):
                    content = content[1:]
                    
                input_io = io.StringIO(content)
                reader = csv.DictReader(input_io)
                return list(reader)
                
        return []

    def add_resource(self, resource_name: str, data: List[Dict[str, Any]], schema: Optional[Dict[str, Any]] = None, path: Optional[str] = None):
        """
        Add a resource to the data package.
        If resource exists, it updates it.
        If path is provided, data is written to that path (relative to descriptor) as CSV.
        """
        # Define resource descriptor
        resource_descriptor = {
            "name": resource_name,
        }
        
        if schema:
            resource_descriptor["schema"] = schema

        if path:
            target_file_path = f"{os.path.dirname(self.descriptor_path)}/{path}"
            
            if path.endswith(".json"):
                # Write JSON
                import json
                content = json.dumps(data, indent=2, ensure_ascii=False)
                
                with self.repository.open_file(target_file_path, "w") as f:
                    f.write(content)
                
                resource_descriptor["path"] = path
                resource_descriptor["format"] = "json"
                resource_descriptor["mediatype"] = "application/json"
            else:
                # Write CSV
                import csv
                import io
                
                # Determine fieldnames
                if data:
                    fieldnames = list(data[0].keys())
                elif schema and "fields" in schema:
                    fieldnames = [f["name"] for f in schema["fields"]]
                else:
                    fieldnames = []

                # Create CSV content
                output = io.StringIO()
                if fieldnames:
                    # Use QUOTE_ALL to ensure robust handling of newlines and special characters in messages
                    # This is safer for Excel/Sheets import.
                    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                    writer.writerows(data)
                
                # Write with BOM for Excel compatibility (UTF-8-SIG equivalent logic)
                with self.repository.open_file(target_file_path, "w") as f:
                    # Add BOM
                    f.write('\ufeff')
                    f.write(output.getvalue())
                
                resource_descriptor["path"] = path
                resource_descriptor["format"] = "csv"
                resource_descriptor["mediatype"] = "text/csv"
        else:
            # Inline data
            resource_descriptor["data"] = data

        # Remove existing resource if present to avoid duplicates/conflicts
        if self.package.get_resource(resource_name):
            self.package.remove_resource(resource_name)

        self.package.add_resource(resource_descriptor)

    def save(self):
        """
        Save the datapackage.json and any resources if needed.
        Currently we save the descriptor to the repository.
        """
        # Ensure metadata directory exists
        if not self.repository.exists(self.metadata_dir):
            # We need to create the directory. Since RepositoryPort is abstract,
            # we rely on the implementation or assume we can write files relative to it.
            # If the repo is a filesystem one, it should handle paths.
            # But wait, standard RepositoryPort doesn't have mkdir.
            # We assume for now that writing to a path with subdirs might work or fail.
            # Given this is "wip", we might need to rely on the underlying mechanism.
            pass

        # Package.descriptor is a dict
        descriptor = self.package.descriptor
        
        json_content = json.dumps(descriptor, indent=4, ensure_ascii=False)
        
        with self.repository.open_file(self.descriptor_path, "w") as f:
            f.write(json_content)
