
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional


class CliContextPort(ABC):
    """
    CLI context port.
    """
    @property
    @abstractmethod
    def raw_args(self) -> List[str]:
        """
        Gets the raw arguments passed to the context.
        """
        ...

    @property
    @abstractmethod
    def unprocessed_args(self) -> List[str]:
        """
        Gets the list of arguments that have not yet been processed.
        """
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
    """
    Port interface defining a strategy that can modify or execute upon a CLI context.
    """
    @abstractmethod
    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Executes the strategy against the provided CLI context.
        """
        ...


class PromptChoiceAwarePort(ABC):
    """
    Port for classes that require a prompt function to let the user choose among options.
    """
    @abstractmethod
    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        """
        Injects the prompt choice callable into the implementing class.
        """
        ...
