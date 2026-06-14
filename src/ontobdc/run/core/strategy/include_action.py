from ontobdc.run.domain.port.contex import CliContextStrategyPort, CliContextPort


class IncludeActionStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        flags = ["-a", "-auc", "-uca", "--all"]
        found_flags = [flag for flag in flags if flag in unprocessed_args]
        
        if found_flags:
            context.add_parameter("include_action", {
                "value": True, 
                "uri": "org.ontobdc.domain.context.strategy.flag.include_action"
            })
            context.clear_parameters(["-a", "-auc", "-uca", "--all"])
            
        return context
