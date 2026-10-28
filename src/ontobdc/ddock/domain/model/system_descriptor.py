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


class SystemSource(BaseModel):
    """
    Where the ddock of the system goes and where it comes from.

    ``local`` is the folder inside the container that receives it: the folder
    of the zip of the ddock that becomes the application. ``remote`` is the
    address of the GitHub repository of the ddock it is downloaded from,
    empty meaning the official OntoBDC dDock.
    """

    local: str
    remote: str = ""


class SystemDescriptor(BaseModel):
    """
    What ``system.obdc`` says about the system to install.

    ``source`` names the folder that receives the ddock and the repository it
    comes from; the host of each package is merged into it. ``packages`` are
    the GitHub addresses of the features to add.
    """

    python_dependencies: List[PythonDependency] = Field(default_factory=list)
    source: SystemSource
    packages: List[str] = Field(default_factory=list)
