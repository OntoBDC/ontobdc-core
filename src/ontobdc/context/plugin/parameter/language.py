from ontobdc.shared.facade.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class ViewLanguageStrategy(ParameterPort, CliContextStrategyPort):
    """Normalize an explicit view language while preserving resolved context values."""

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.view.parameter.language",
        version="0.12.0",
        name="language",
        description=(
            "Resolve the language requested for a generated view, preserving the "
            "language already resolved by the current context when omitted."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_language = context.get_parameter_value("language")
        if raw_language is None:
            return context

        language = str(raw_language).strip()
        if language:
            context.set_parameter_value("language", language)

        return context
