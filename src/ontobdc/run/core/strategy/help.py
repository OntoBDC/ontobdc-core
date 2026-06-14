
from ontobdc.run.domain.port.contex import CliContextStrategyPort, CliContextPort


class HelpStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "-h" in unprocessed_args or "--help" in unprocessed_args:
            context.add_parameter("help", {"value": True, "uri": "org.ontobdc.domain.context.strategy.flag.help"})
            context.clear_parameters(["-h", "--help"])
            
        return context