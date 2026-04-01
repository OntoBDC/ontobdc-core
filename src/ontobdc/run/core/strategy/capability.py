from typing import List, Optional
from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class CapabilityIdStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args = context.unprocessed_args
        
        if "--id" in unprocessed_args:
            try:
                idx = unprocessed_args.index("--id")
                if idx + 1 < len(unprocessed_args):
                    capability_id = unprocessed_args[idx + 1]
                    # Check if the next argument is a flag (starts with -)
                    if capability_id.startswith("-"):
                        context.add_parameter("capability_id", {"value": None, "uri": "org.ontobdc.domain.context.strategy.parameter.capability_id"})
                    else:
                        context.add_parameter("capability_id", {"value": capability_id, "uri": "org.ontobdc.domain.context.strategy.parameter.capability_id"})
                        context.clear_parameters([capability_id])
                else:
                    context.add_parameter("capability_id", {"value": None, "uri": "org.ontobdc.domain.context.strategy.parameter.capability_id"})
            except ValueError:
                pass
            
            context.clear_parameters(["--id"])
            
        return context