
from abc import abstractmethod
from typing import Dict, Any, List


class InputParamChecker:

    @property
    def params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for param_id, value in self._get_params().items():
            if param_id in [param["@id"] for param in self._get_expected_params()]:
                params[param_id] = value

        return params

    def check(self) -> None:
        # print(self._get_params())
        pass

    def _parse_args(self, args: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Parse the input arguments.
        """
        params: Dict[str, Dict[str, Any]] = {}
        for arg in args:
            if arg.startswith("--"):
                params[arg[2:]] = {}
            else:
                params["default"] = arg

        return params

    @abstractmethod
    def _get_params(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def _get_expected_params(self) -> List[Dict[str, Any]]:
        ...
