from abc import abstractmethod
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import UnresolvedParamResolver
from ontobdc.shared.domain.model.health import HealthCheck
from ontobdc.shared.domain.port.resolver import DynamicParamResolverPort
from ontobdc.shared.domain.port.capability import (
    CapabilityPort,
    HealthCheckCapabilityPort,
    PersisterCapabilityPort,
    ReadOnlyCapabilityPort,
    TransactionCapabilityPort,
    TransformationCapabilityPort,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.adapter.logging import CapabilityLoggingSupport


class Capability(CapabilityPort):
    METADATA: CapabilityMetadata

    @property
    def metadata(self) -> CapabilityMetadata:
        return self.METADATA

    def tags(self, lang: str = "en") -> List[str]:
        """
        Returns the tags in the specified language.
        """
        if isinstance(self.metadata.tags, dict):
            return self.metadata.tags.get(lang, self.metadata.tags.get("en", []))
        return self.metadata.tags

    def check_inputs(self, context: CliContextPort) -> None:
        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            required = spec.get("required", False)
            if required and not context.has_parameter(prop):
                raise ValueError(f"Missing required input: {prop}")
            
            if context.has_parameter(prop):
                input_value = context.get_parameter_value(prop)
                prop_type = spec.get("type", None)
                
                if prop_type:
                    valid = True
                    if isinstance(prop_type, type):
                        if not isinstance(input_value, prop_type):
                            valid = False
                    elif prop_type == "integer":
                        if not isinstance(input_value, int):
                            valid = False
                    elif prop_type == "string":
                        if not isinstance(input_value, str):
                            valid = False
                    elif prop_type == "boolean":
                        if not isinstance(input_value, bool):
                            valid = False
                    elif prop_type == "object":
                        if not isinstance(input_value, dict):
                            valid = False

                    if not valid:
                        raise ValueError(f"Input {prop} has type {type(input_value)}, expected {prop_type}") 

                # Check verification strategies
                for check in spec.get("check", []):
                    strategy = check
                    if isinstance(strategy, type):
                        strategy = strategy()

                    if not strategy.verify(prop, input_value, context):
                        raise ValueError(f"Input {prop} failed verification strategy {strategy.__class__.__name__}")

    def resolve_inputs(
        self,
        context: CliContextPort,
        resolver: DynamicParamResolverPort,
    ) -> None:
        """
        Resolve the inputs of the capability through the given resolver.

        The concrete resolver is composed by the caller: a capability depends
        on the resolution contract, never on an implementation of it.
        """
        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            prop_uri: str = spec.get("uri", None)

            if not isinstance(prop_uri, str) or not prop_uri.strip():
                continue

            resolver.resolve(context, prop_uri, prop)

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None

    @abstractmethod
    def label(self, lang: str = "en") -> str:
        """
        Returns the label of the capability in the specified language.
        :param lang: The language to use.
        :return: The label of the capability in the specified language.
        """
        ...

    @abstractmethod
    def description(self, lang: str = "en") -> str:
        """
        Returns the description of the capability in the specified language.
        :param lang: The language to use.
        :return: The description of the capability in the specified language.
        """
        ...

    def __str__(self) -> str:
        return f"{self.metadata.id}"

    def __repr__(self) -> str:
        return f"{self.metadata.id}"


class TransformationCapability(Capability, TransformationCapabilityPort):
    pass


class TransactionCapability(Capability, TransactionCapabilityPort):
    pass


class PersisterCapability(Capability, PersisterCapabilityPort):
    pass


class DataLoaderCapability(Capability, ReadOnlyCapabilityPort):
    pass


class HealthCheckCapability(Capability, HealthCheckCapabilityPort):
    """
    Capability that reports the verifications it runs and repairs nothing.

    A subclass says only which checks it runs, in ``checks()``. Turning
    them into the result a caller reads is the same work every time, so it
    is done once here: the listing, in the order the subclass reported it,
    and whether every one of them holds.
    """

    CHECKS_KEY: ClassVar[str] = "checks"
    HEALTHY_KEY: ClassVar[str] = "healthy"

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Run every check this capability reports and return the listing.
        """
        checks: List[HealthCheck] = self.checks(context)

        return {
            self.CHECKS_KEY: checks,
            self.HEALTHY_KEY: all(check.passed for check in checks),
        }


class CapabilityExecutor:
    OUTPUT_PATH_KEY: ClassVar[str] = "output_path"

    @staticmethod
    def execute(
        capability: Capability,
        context: CliContextPort,
        resolver: Optional[DynamicParamResolverPort] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the given capability with the provided context.

        :param capability: The capability to execute.
        :param context: The context to pass to the capability.
        :param resolver: Resolver used for inputs declaring an ontology URI.
            Defaults to the null resolver, which leaves them untouched.
        :param output_path: Optional value to temporarily inject as the
            canonical ``output_path`` key in the context during execution.
            The original value (or absence) is restored afterwards.
        :return: The output of the capability execution.
        """
        if resolver is None:
            resolver = UnresolvedParamResolver()

        key: str = CapabilityExecutor.OUTPUT_PATH_KEY
        had_output_path: bool = context.has_parameter(key)
        original_output_path: Any = context.get_parameter_value(key)
        if output_path is not None:
            context.set_parameter_value(key, output_path)

        try:
            if isinstance(capability, CapabilityPort):
                capability.resolve_inputs(context, resolver)

                capability.check_inputs(context)

            # Debug entry trace (only for side-effecting capability families,
            # matching the families logged on success).  Uses the same metadata
            # resolution contract as INFO: log_message["debug"][lang] first.
            side_effecting: bool = (
                isinstance(capability, TransformationCapabilityPort)
                or isinstance(capability, TransactionCapabilityPort)
                or isinstance(capability, PersisterCapabilityPort)
            )
            if side_effecting:
                CapabilityLoggingSupport.log_entry(capability, context)

            try:
                result: Dict[str, Any] = capability.execute(context)
            except BaseException as exc:
                if side_effecting:
                    CapabilityLoggingSupport.log_exception(capability, context, exc)
                raise

            if side_effecting:
                CapabilityLoggingSupport.log_success(capability, context, result)

            return result
        finally:
            if output_path is not None:
                if had_output_path:
                    context.set_parameter_value(key, original_output_path)
                else:
                    context.delete_parameter(key)
