
from typing import List, Optional
from ontobdc.module.resource.adapter.repository import SimpleFileRepository
from ontobdc.run.core.port.contex import CliContextStrategyPort, CliContextPort


class RootPathStrategy(CliContextStrategyPort):
    def execute(self, context: CliContextPort) -> CliContextPort:
        unprocessed_args: List[str] = context.unprocessed_args
        root_path: str = context.root_path
        found_flag: Optional[bool] = None
        
        # Check for --root-path or --repository (priority to --root-path)
        if "--root-path" in unprocessed_args:
            found_flag = "--root-path"
        elif "--repository" in unprocessed_args:
            found_flag = "--repository"
            
        if found_flag:
            idx = unprocessed_args.index(found_flag)
            if idx + 1 < len(unprocessed_args):
                val = unprocessed_args[idx + 1]
                # Check if value looks like another flag
                if not val.startswith("-"):
                    root_path = val
                    context.clear_parameters([found_flag, val])
                else:
                    # Flag present but no value (next arg is a flag), fallback to default
                    # Just remove the flag, keep default root_path
                    context.clear_parameters([found_flag])
            else:
                # Flag at end, fallback to default
                context.clear_parameters([found_flag])

        # Always set root_path parameter (either from flag or default cwd)
        context.add_parameter("repository", {
            "value": SimpleFileRepository(root_path), 
            "uri": "org.ontobdc.domain.context.strategy.parameter.root_path",
            "param_uri": "org.ontobdc.domain.resource.document.repository.incoming"
        })
            
        return context
