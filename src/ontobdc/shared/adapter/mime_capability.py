import inspect
from typing import Any, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.capability import CapabilityPort


class MimeCapabilityMap:
    """
    The capability a request maps explicitly to a MIME type.

    A request that already knows how a file of some MIME type is to be
    handled carries, under a context parameter of its own, a mapping from
    MIME types to capability classes. A chain of responsibilities is only
    run for the files that mapping says nothing about.
    """

    @staticmethod
    def capability_type(
        context: CliContextPort,
        key: str,
        mime_type: Optional[str],
    ) -> Optional[Type[CapabilityPort]]:
        """
        Return the capability class the context maps to ``mime_type`` under
        ``key``, or None when it maps none (no mapping, no MIME type, or a
        MIME type the mapping does not name).

        Raises:
            TypeError: the mapping is not a dict of MIME types to capability
                classes.
        """
        capabilities_by_mime: Any = context.get_parameter_value(key)
        if capabilities_by_mime is None:
            return None
        if not isinstance(capabilities_by_mime, dict):
            raise TypeError(
                f"'{key}' must map MIME types to capability classes; "
                f"got {type(capabilities_by_mime)!r}."
            )

        if mime_type is None or mime_type not in capabilities_by_mime:
            return None

        capability_type: Any = capabilities_by_mime[mime_type]
        if not inspect.isclass(capability_type) or not issubclass(
            capability_type, CapabilityPort
        ):
            raise TypeError(
                f"'{key}' entry for '{mime_type}' must be a capability class; "
                f"got {capability_type!r}."
            )
        return capability_type
