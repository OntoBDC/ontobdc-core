
import os
import tempfile
from sismic.model import Statechart
from sismic.io import import_from_yaml
from ontobdc.shared.domain.port.machine import StatechartRepositoryPort


class LocalStatechartRepository(StatechartRepositoryPort):
    """
    Repository to load the Sismic Statechart from the local filesystem.
    """
    def __init__(self, filepath: str):
        self._filepath: str = filepath

    def get_statechart(self) -> Statechart:
        import yaml
        
        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
                
            def remove_descriptions(node):
                if isinstance(node, dict):
                    # We need to iterate over a copy of the items so we can delete keys safely
                    for key, value in list(node.items()):
                        if key == 'description':
                            del node[key]
                        elif isinstance(value, (dict, list)):
                            remove_descriptions(value)
                elif isinstance(node, list):
                    for item in node:
                        remove_descriptions(item)
                return node
                
            cleaned_data = remove_descriptions(raw_data)
            
            # Sismic's import_from_yaml needs a filepath or file-like object
            # but we can't easily pass the dict directly to it in all versions,
            # so we write the cleaned dict to a temp file and load it.
            fd, temp_path = tempfile.mkstemp(suffix='.yaml')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                    yaml.dump(cleaned_data, tmp)
                return import_from_yaml(filepath=temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise FileNotFoundError(f"Statechart file not found or invalid: {self._filepath}") from e

    def __str__(self) -> str:
        return f"LocalStatechartRepository(filepath={self._filepath})"
