
from ontobdc.run.domain.port.contex import CliContextStrategyPort, CliContextPort


class ExportStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--export" in unprocessed_args:
            idx = unprocessed_args.index("--export")
            if idx + 1 < len(unprocessed_args):
                export_format = unprocessed_args[idx + 1]
                
                if export_format not in ["json", "rich"]:
                    raise ValueError(f"Invalid export format: '{export_format}'. Must be 'json' or 'rich'.")
                
                context.add_parameter("export", {"value": export_format, "uri": "org.ontobdc.domain.context.strategy.parameter.export"})
                context.clear_parameters(["--export", export_format])
            else:
                 raise ValueError("Missing value for --export. Must be 'json' or 'rich'.")
            
        return context
