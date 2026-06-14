
class IntentLanguageNotSupportedException(Exception):
    """
    Exception for when the intent language is not supported.
    """
    IDENTIFIER = "org.ontobdc.domain.resource.capability.exception.intent.language_not_supported"
    TITLE = "Language Not Supported"

    def __init__(self, message: str):
        super().__init__(message)


class IntentScoreTooLowException(Exception):
    """
    Exception for when the intent score is too low.
    """
    IDENTIFIER = "org.ontobdc.domain.resource.capability.exception.intent.score_too_low"
    TITLE = "Intent Score Too Low"

    def __init__(self, message: str):
        super().__init__(message)


class NoValidCapabilitiesException(Exception):
    """
    Exception for when no valid capabilities are available.
    """
    IDENTIFIER = "org.ontobdc.domain.resource.capability.exception.no_valid_capabilities"
    TITLE = "No Valid Capabilities"

    def __init__(self, message: str):
        super().__init__(message)


class UserCanceledCapabilitySelectionException(Exception):
    """
    Exception for when user cancels or skips capability selection.
    """
    IDENTIFIER = "org.ontobdc.domain.resource.capability.exception.user_canceled_capability_selection"
    TITLE = "User Canceled Capability Selection"

    def __init__(self, message: str):
        super().__init__(message)

