

class OntoBDCPathNotFound(FileNotFoundError):
    def __init__(self, path: str) -> None:
        super().__init__(f"org.ontobdc.domain.resource.exception.path_not_found: {path}")
        self.path = path
