from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort

class ActionOnlyStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--action-only" in unprocessed_args:
            context.add_parameter("action_only", {
                "value": True, 
                "uri": "org.ontobdc.domain.context.strategy.flag.action_only"
            })
            context.clear_parameters(["--action-only"])
            
        return context
