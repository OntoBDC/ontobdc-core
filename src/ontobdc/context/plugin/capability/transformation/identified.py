from typing import Any, Dict

from ontobdc.context.adapter.repository import EntityLearningStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.learning_state import EntityLearningProcessState
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort


class IdentifiedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.context.plugin.capability.transformation.target.identified",
        version="1.0.0",
        name="Context learning transformation to Identified",
        description="Store the source file as the identified step of the entity learning pipeline.",
        author=["TRAE"],
        tags=["context", "learning", "identified"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Context learning transformation to Identified"

    def description(self, lang: str = "en") -> str:
        return "Store the source file as the identified step of the entity learning pipeline."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        source_resource: LocalContextFileResource = step_repository.reload(EntityLearningProcessState.UNDEFINED)
        identified_path = step_repository.write_text_file(
            state=EntityLearningProcessState.IDENTIFIED,
            content=(
                "{\n"
                f'  "name": "{source_resource.name}",\n'
                f'  "path": "{str(source_resource.path).replace("\\", "\\\\")}",\n'
                f'  "uri": "{source_resource.path.as_uri()}",\n'
                f'  "mimetype": "{source_resource.mimetype}"\n'
                "}\n"
            ),
            file_type="json",
        )
        context.set_parameter_value("resource", LocalContextFileResource(identified_path))
        return {
            "resulting_state": EntityLearningProcessState.IDENTIFIED,
            "path": str(identified_path),
        }
