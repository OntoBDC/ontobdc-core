from pathlib import Path
from typing import Dict, List, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.adapter.machine import EntityLearningStateTransitionHandler
from ontobdc.context.adapter.repository import EntityLearningStepRepository


class ContextLearnFromCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="learn_from",
        logical_component="context",
        description="Learn an entity profile from a file or directory.",
        arguments=[
            {
                "accepts": ["--learn-from"],
                "valued": True,
                "description": "Learn an entity profile from a file or directory.",
                "usage": "ontobdc context --entity <entity_uri> --learn-from <file_path>",
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Target entity URI for the learning flow.",
                "usage": "ontobdc context --entity <entity_uri> --learn-from <file_path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 5 and args[0] == "context" and "--entity" in args and "--learn-from" in args

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        entity_uri, learn_from_path = self._parse_arguments()
        if ":" not in entity_uri:
            raise CliCommandArgumentException(f"Invalid entity_uri: {entity_uri}")

        resolved_path: Path = Path(learn_from_path).expanduser().resolve()
        if not resolved_path.exists():
            raise CliCommandArgumentException(f"Invalid learn-from path: {learn_from_path}")

        source_files: List[Path] = self._collect_source_files(resolved_path)
        if not source_files:
            raise CliCommandArgumentException(f"No PDF files found in '{resolved_path}'.")

        self._request.context.set_parameter_value("entity_uri", entity_uri)
        self._request.context.set_parameter_value("learn_from_path", str(resolved_path))
        self._request.context.set_parameter_value(
            "learn_source_files",
            [str(source_file) for source_file in source_files],
        )
        return True

    def run(self) -> CommandResponse:
        entity_uri: str = str(self._request.context.get_parameter_value("entity_uri")).strip()
        source_files: List[str] = list(self._request.context.get_parameter_value("learn_source_files"))
        results: List[Dict[str, object]] = []

        try:
            for source_file in source_files:
                step_repository = EntityLearningStepRepository(
                    root_path=str(self._request.context.root_path),
                    source_path=source_file,
                )
                self._request.context.set_parameter_value("step_repository", step_repository)
                self._request.context.set_parameter_value("learn_source_path", source_file)

                response: CommandResponse = EntityLearningStateTransitionHandler(
                    context=self._request.context,
                ).execute()
                results.append(
                    {
                        "source_file": source_file,
                        "response": response.content,
                    }
                )

            return CommandResponse(
                title="Context Entity Learned",
                description=f"Processed {len(results)} learning source file(s) for entity '{entity_uri}'.",
                content={
                    "entity_uri": entity_uri,
                    "processed_files": len(results),
                    "results": results,
                },
            )
        except Exception as exc:
            return ExceptionCommandResponse(
                title="Context Entity Learning Failed",
                description=f"Could not learn entity '{entity_uri}' from the provided source path.",
                content={
                    "entity_uri": entity_uri,
                    "source_files": source_files,
                    "error": str(exc),
                },
            )

    def _parse_arguments(self) -> Tuple[str, str]:
        command_args: List[str] = list(self._request.command_args)
        if len(command_args) != 4:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --entity <entity_uri> --learn-from <file_path>"
            )

        argument_pairs = {
            command_args[index]: command_args[index + 1]
            for index in range(0, len(command_args), 2)
        }
        entity_uri: str = str(argument_pairs.get("--entity", "")).strip()
        learn_from_path: str = str(argument_pairs.get("--learn-from", "")).strip()
        if not entity_uri or not learn_from_path:
            raise CliCommandArgumentException(
                "Usage: ontobdc context --entity <entity_uri> --learn-from <file_path>"
            )

        return entity_uri, learn_from_path

    def _collect_source_files(self, resolved_path: Path) -> List[Path]:
        if resolved_path.is_file():
            return [resolved_path] if resolved_path.suffix.lower() == ".pdf" else []

        return sorted(
            file_path
            for file_path in resolved_path.rglob("*.pdf")
            if file_path.is_file()
        )
