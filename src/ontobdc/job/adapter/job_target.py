from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple, Type

from ontobdc.run.adapter.fsm import FsmIdLocator
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.storage_addons import StorageAddons


@dataclass(frozen=True)
class JobTarget:
    """
    What a procedure executes: a finite state machine or a capability, with the arguments that run it.
    """

    id: str
    kind: str
    argv: Tuple[str, ...]
    # The folder of the addon the machine comes from, when it is not one of OntoBDC's own.
    addon: Optional[str] = None

    @classmethod
    def locate(cls, target_id: str) -> "JobTarget":
        """
        The machine or the capability that has the id, looked for in every plugin of every module and, when nothing there
        has the id, in the addons installed in the storage.

        Raises:
            LookupError: nothing has the id, or both a machine and a capability do.
        """
        capability: Optional[Type[Any]] = CapabilityLoader().get(target_id)
        machine: Optional[Tuple[Any, Type[Any]]] = FsmIdLocator().locate(target_id)
        if capability is not None and machine is not None:
            raise LookupError(f"Both a capability and a machine have the id {target_id}.")
        if machine is not None:
            return cls(id=target_id, kind="fsm", argv=("run", "--fsm", str(machine[0])))
        if capability is not None:
            return cls(id=target_id, kind="capability", argv=("run", "--capability", target_id))

        addons: List[Path] = StorageAddons.installed(Path(StorageFileLocator.resolve()))
        addon: Path
        for addon in addons:
            statechart: Optional[Path] = FsmIdLocator.addon_statechart(addon, target_id)
            if statechart is not None:
                return cls(id=target_id, kind="fsm", argv=("run", "--fsm", str(statechart)), addon=str(addon))

        raise LookupError(
            f"No machine and no capability has the id {target_id}, and none of the addons installed in the storage "
            f"({', '.join(addon.name for addon in addons) or 'none'}) has a machine with that id (a machine of the addon "
            "NAME is <NAME>.plugin.machine.<folder of the machine>). Install the addon with `ontobdc init --addon "
            "<folder or address>`."
        )

    def arguments(self, container_path: str, parameters: List[Tuple[str, str]]) -> List[str]:
        """
        The arguments that run the target on the container, with the parameters of the job as flags.
        """
        arguments: List[str] = [*self.argv, "--container", container_path]
        name: str
        value: str
        for name, value in parameters:
            arguments.extend([f"--{name.replace('_', '-')}", value])

        return arguments
