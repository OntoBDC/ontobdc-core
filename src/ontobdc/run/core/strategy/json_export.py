from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class JsonExportStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--json" in unprocessed_args:
            context.add_parameter("json_export", {"value": True, "uri": "org.ontobdc.domain.context.strategy.flag.json_export"})
            context.clear_parameters(["--json"])
            
        return context