from typing import List, Optional

from pydantic import BaseModel, Field


class PythonDependency(BaseModel):
    """
    A Python package the system needs, at the version the descriptor asks for
    when it asks for one.
    """

    name: str
    version: Optional[str] = None

    def requirement(self) -> str:
        """
        The requirement ``pip`` installs it by: ``name==version``, or the bare
        name when no version is asked for.
        """
        return f"{self.name}=={self.version}" if self.version else self.name


class SystemDescriptor(BaseModel):
    """
    What ``system.obdc`` says about the system to install.

    ``source`` is the folder of the ddock zip that becomes the application:
    it is moved to the same place under the project, and the host of each
    package is merged into it. ``packages`` are the GitHub addresses of the
    features to add.
    """

    python_dependencies: List[PythonDependency] = Field(default_factory=list)
    source: str
    packages: List[str] = Field(default_factory=list)
