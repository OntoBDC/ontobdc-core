class ParamResolverStrategyNotFoundError(RuntimeError):
    """
    Raised when no discovered strategy answers for a declared parameter URI.

    Resolution failing loudly is deliberate: an input declaring a URI that
    nothing resolves is a missing plugin, not an input to leave untouched.
    """

    def __init__(self, parameter_uri: str, parameter_name: str) -> None:
        super().__init__(
            f"No parameter resolver strategy supports the uri "
            f"'{parameter_uri}' declared by the input '{parameter_name}'."
        )
        self.parameter_uri: str = parameter_uri
        self.parameter_name: str = parameter_name
