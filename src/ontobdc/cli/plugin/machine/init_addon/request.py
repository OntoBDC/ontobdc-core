from typing import ClassVar, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter


class CliInitAddonRequest:
    """
    What the addition of an addon is asked with: the folder of the addon on this machine, or the address of its folder in
    a repository of GitHub, in the parameter ``--addon``.
    """

    SOURCE_KEY: ClassVar[str] = "addon_source"
    SOURCE_FLAG: ClassVar[str] = "--addon"
    # What the state that locates the addon leaves for the one that adds it: the folder of the addon on this machine.
    FOLDER_KEY: ClassVar[str] = "addon_folder"

    @classmethod
    def source(cls, context: CliContextPort) -> str:
        """
        The folder or the address of the addon.

        Raises:
            ValueError: the parameter ``--addon`` was not given.
        """
        value: Optional[str] = RequiredParameter.optional(context, cls.SOURCE_KEY)
        if value is None or not value.strip():
            raise ValueError(f"The parameter {cls.SOURCE_FLAG} is missing: give the folder or the address of the addon.")

        return value.strip()
