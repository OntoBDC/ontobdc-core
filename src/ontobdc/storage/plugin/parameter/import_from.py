
from pathlib import Path
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class ImportFromPathStrategy(ParameterPort, CliContextStrategyPort):
    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.storage.capability.incoming.import_from",
        version="0.1.0",
        name="import_from",
        description="Resolve the import source path against the active project root.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=Path,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_path_value: str = str(context.get_parameter_value("import_from") or "").strip()
        if not raw_path_value:
            return context

        candidate_path: Path = Path(raw_path_value).expanduser()
        if not candidate_path.is_absolute():
            candidate_path = Path(str(context.root_path)).expanduser() / candidate_path

        context.set_parameter_value("import_from_path", str(candidate_path.resolve()))
        return context
