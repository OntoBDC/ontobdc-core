
from typing import Any, Callable, List, Optional
from abc import ABC, abstractmethod


class CliContextPort(ABC):

    @property
    @abstractmethod
    def raw_args(self) -> List[str]:
        ...

    @property
    @abstractmethod
    def unprocessed_args(self) -> List[str]:
        ...

    @property
    @abstractmethod
    def is_capability_targeted(self) -> bool:
        """
        Returns True if a specific capability was targeted (via --id).
        """
        ...

    @property
    @abstractmethod
    def target_capability_id(self) -> str | None:
        """
        Returns the targeted capability ID if specified, None otherwise.
        """
        ...

    @property
    @abstractmethod
    def root_path(self) -> str:
        """
        Returns the root path of the repository.
        """
        ...

    @property
    @abstractmethod
    def language(self, fallback: str = None) -> Optional[str]:
        """
        Returns the language of the context.
        Defaults to the system's language.
        :param fallback: The fallback language if the system's language is not available.
        :return: The language of the context, or the fallback if not available.
        """
        ...

    @abstractmethod
    def has_parameter(self, param_key: str) -> bool:
        """
        Returns True if the parameter is set in the context.
        """
        ...

    @abstractmethod
    def get_parameter_value(self, param_key: str) -> Any:
        """
        Retrieves the 'value' of a parameter by its key.
        Returns None if parameter does not exist.
        """
        ...

    @abstractmethod
    def set_parameter_value(self, param_key: str, param_value: Any) -> None:
        """
        Sets the value of a parameter.
        """
        ...

    @abstractmethod
    def delete_parameter(self, param_key: str) -> None:
        """
        Removes a parameter from the context.
        """
        ...

    @abstractmethod
    def clear_parameters(self, param_keys: List[str]) -> None:
        """
        Clears the values of multiple parameters.
        """
        ...

    @abstractmethod
    def reload(self) -> None:
        """
        Reloads the context from the file.
        """
        ...


class CliContextStrategyPort(ABC):
    @abstractmethod
    def execute(self, context: CliContextPort) -> CliContextPort:
        ...


class PromptChoiceAwarePort(ABC):
    @abstractmethod
    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        ...


class PromptRawTextAwarePort(ABC):
    @abstractmethod
    def set_prompt_raw_text(self, prompt_raw_text: Callable[[str], str]) -> None:
        ...
