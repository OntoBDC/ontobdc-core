from ontobdc.run.domain.port.contex import CliContextStrategyPort, CliContextPort

class FileNameStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--file-name" in unprocessed_args:
            idx = unprocessed_args.index("--file-name")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                context.add_parameter("file_name", {
                    "value": val, 
                    "uri": "org.ontobdc.domain.context.strategy.parameter.file_name",
                    "param_uri": "org.ontobdc.domain.resource.input.file.name"
                })
                context.clear_parameters(["--file-name", val])
            else:
                raise ValueError("Missing value for --file-name.")
            
        return context

class FileTypeStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--file-type" in unprocessed_args:
            idx = unprocessed_args.index("--file-type")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                # Split by comma if multiple types are provided
                file_types = [t.strip() for t in val.split(",")]
                context.add_parameter("file_type", {
                    "value": file_types, 
                    "uri": "org.ontobdc.domain.context.strategy.parameter.file_type",
                    "param_uri": "org.ontobdc.domain.resource.input.file.type"
                })
                context.clear_parameters(["--file-type", val])
            else:
                raise ValueError("Missing value for --file-type.")
            
        return context
