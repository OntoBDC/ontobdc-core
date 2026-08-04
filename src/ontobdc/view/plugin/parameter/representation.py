from ontobdc.shared.facade.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class ViewRepresentationStrategy(ParameterPort, CliContextStrategyPort):
    """Resolve the requested visual representation for a generated view."""

    SUPPORTED_REPRESENTATIONS = ("html", "pdf")

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.view.parameter.representation",
        version="0.12.0",
        name="representation",
        description=(
            "Resolve the visual representation requested for a generated view."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_representation = context.get_parameter_value("representation")
        representation = str(raw_representation or "html").strip().lower()

        if representation not in self.SUPPORTED_REPRESENTATIONS:
            supported = ", ".join(self.SUPPORTED_REPRESENTATIONS)
            raise ValueError(
                f"Unsupported view representation: {representation}. "
                f"Supported values: {supported}."
            )

        context.set_parameter_value("representation", representation)
        return context
