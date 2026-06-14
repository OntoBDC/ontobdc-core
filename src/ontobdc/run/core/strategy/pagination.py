from ontobdc.run.domain.port.contex import CliContextStrategyPort, CliContextPort

class PaginationStartStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--start" in unprocessed_args:
            idx = unprocessed_args.index("--start")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                try:
                    int_val = int(val)
                    context.add_parameter("start", {
                        "value": int_val, 
                        "uri": "org.ontobdc.domain.context.strategy.parameter.pagination.start"
                    })
                    context.clear_parameters(["--start", val])
                except ValueError:
                    raise ValueError(f"Invalid value for --start: '{val}'. Must be an integer.")
            else:
                raise ValueError("Missing value for --start. Must be an integer.")
            
        return context

class PaginationLimitStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--limit" in unprocessed_args:
            idx = unprocessed_args.index("--limit")
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                try:
                    int_val = int(val)
                    context.add_parameter("limit", {
                        "value": int_val, 
                        "uri": "org.ontobdc.domain.context.strategy.parameter.pagination.limit"
                    })
                    context.clear_parameters(["--limit", val])
                except ValueError:
                    raise ValueError(f"Invalid value for --limit: '{val}'. Must be an integer.")
            else:
                raise ValueError("Missing value for --limit. Must be an integer.")
            
        return context
