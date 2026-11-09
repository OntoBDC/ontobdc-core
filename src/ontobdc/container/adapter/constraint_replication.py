from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

import yaml

from ontobdc.cli.adapter.init_config import InitContainerFiles


class ConstraintReplication:
    """
    The constraints of the application, replicated into the config of the container.

    The application keeps its constraints in its own config (the ``constraint`` key of the asset
    ``config.yaml``, put there from ``system.obdc``) and hands that config, as text, to the commands that
    refresh and check the container (``--config <body>``). The container keeps the copy it reads in its
    ``.__ontobdc__/config.yaml``, under the same key. The copy is exact: what the container had under
    ``constraint`` is replaced by what the body declares, and gone when the body declares none, so any
    change made to the copy in the container is discarded the next time it is replicated.

    A command given no body has nothing to replicate and nothing to compare: the container is left as it is.
    """

    KEY: ClassVar[str] = "constraint"

    @classmethod
    def declared(cls, body: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        The constraints the body declares: an empty mapping when it declares none, and ``None`` when
        there is no body at all.

        Raises:
            ValueError: the body is not a YAML (or JSON) mapping, or declares its constraints as something
                other than a mapping.
        """
        if body is None or not body.strip():
            return None

        try:
            loaded: Any = yaml.safe_load(body)
        except yaml.YAMLError as error:
            raise ValueError(f"The config body is not valid YAML: {error}") from error

        if loaded is None:
            return {}

        if not isinstance(loaded, dict):
            raise ValueError("The config body must be a mapping.")

        constraints: Any = loaded.get(cls.KEY)
        if constraints is None:
            return {}

        if not isinstance(constraints, dict):
            raise ValueError(f'The config body declares "{cls.KEY}" as something other than a mapping.')

        return constraints

    @classmethod
    def in_container(cls, root_path: str) -> Dict[str, Any]:
        """The constraints the config of the container holds; empty when it holds none."""
        held: Any = InitContainerFiles.read_config(str(Path(root_path).expanduser().resolve())).get(cls.KEY)
        return held if isinstance(held, dict) else {}

    @classmethod
    def is_replicated(cls, root_path: str, body: Optional[str]) -> bool:
        """Whether the container holds what the body declares; true when there is no body to compare with."""
        declared: Optional[Dict[str, Any]] = cls.declared(body)
        if declared is None:
            return True

        return cls.in_container(root_path) == declared

    @classmethod
    def replicate(cls, root_path: str, body: Optional[str]) -> bool:
        """
        Put what the body declares in the config of the container. Returns whether the config was written;
        nothing is written when there is no body, or the container already holds the same.
        """
        declared: Optional[Dict[str, Any]] = cls.declared(body)
        if declared is None or cls.in_container(root_path) == declared:
            return False

        root: str = str(Path(root_path).expanduser().resolve())
        config: Dict[str, Any] = InitContainerFiles.read_config(root)
        if declared:
            config[cls.KEY] = declared
        else:
            config.pop(cls.KEY, None)

        InitContainerFiles.write_config(root, config)
        return True
