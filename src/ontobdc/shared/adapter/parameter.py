from typing import Any, Optional

from ontobdc.cli.domain.port.context import CliContextPort


class RequiredParameter:
    """
    Reads a value the context is supposed to carry, without inventing one.

    A caller that needs a value asks for it and gets it or an error naming
    what is missing; a caller that can go on without it asks for the optional
    reading and decides for itself. Neither substitutes a value the context
    does not hold: a container path that came out as an empty string is a
    path to the current directory once resolved, which is how an operation
    ends up running somewhere nobody asked for.
    """

    @staticmethod
    def of(context: CliContextPort, name: str) -> str:
        """
        Return the value the context carries under the given name.

        Raises when the context carries nothing usable under it.
        """
        value: Optional[str] = RequiredParameter.optional(context, name)
        if value is None:
            raise ValueError(
                f"Required parameter is missing from the command context: "
                f"{name}"
            )

        return value

    @staticmethod
    def optional(context: CliContextPort, name: str) -> Optional[str]:
        """
        Return the value the context carries under the given name, or None.
        """
        value: Any = context.get_parameter_value(name)
        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()
