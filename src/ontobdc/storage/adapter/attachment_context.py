from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment_error import ContainerAttachError
from ontobdc.storage.adapter.attachment_metadata import (
    is_storage_index_attached,
)
from ontobdc.storage.adapter.attachment_plan import (
    ATTACH_COMPLETED_PARAMETER,
    ATTACH_ERROR_PARAMETER,
    ATTACH_PLAN_PARAMETER,
    plan,
    required_resolved_plan,
)
from ontobdc.storage.adapter.attachment_transaction import (
    discard_attachment_backup,
    restore_attachment,
)


def attach_context(context: CliContextPort) -> Dict[str, Any]:
    attachment_plan = required_resolved_plan(context)
    for parameter_name in (
        "container",
        "dataset_path",
        "container_update_completed",
        "container_html_view_updated",
        ATTACH_ERROR_PARAMETER,
    ):
        context.delete_parameter(parameter_name)
    context.set_parameter_value(
        "container_id",
        attachment_plan["target_container_id"],
    )
    context.set_parameter_value(
        "container_path",
        attachment_plan["container_path"],
    )
    return {
        "container_id": attachment_plan["target_container_id"],
        "container_path": attachment_plan["container_path"],
    }


def is_context_attached(context: CliContextPort) -> bool:
    attachment_plan = plan(context)
    if attachment_plan is None or not is_storage_index_attached(context):
        return False
    return (
        str(context.get_parameter_value("container_id") or "")
        == attachment_plan["target_container_id"]
        and Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        == Path(attachment_plan["container_path"]).resolve()
        and context.get_parameter_value("dataset_path") is None
        and context.get_parameter_value("container_update_completed") is None
        and context.get_parameter_value("container_html_view_updated") is None
    )


def complete_attachment(context: CliContextPort) -> Dict[str, Any]:
    attachment_plan = required_resolved_plan(context)
    if not is_context_attached(context):
        raise ContainerAttachError(
            "The container attachment could not be validated after updating "
            "the execution context."
        )
    context.set_parameter_value(ATTACH_COMPLETED_PARAMETER, True)
    discard_attachment_backup(attachment_plan)
    context.set_parameter_value(ATTACH_PLAN_PARAMETER, attachment_plan)
    return {
        "source_container_id": attachment_plan["source_container_id"],
        "container_id": attachment_plan["target_container_id"],
        "container_path": attachment_plan["container_path"],
        "datasets_attached": len(attachment_plan["datasets"]),
    }


def is_container_attached(context: CliContextPort) -> bool:
    return bool(context.get_parameter_value(ATTACH_COMPLETED_PARAMETER)) and (
        is_context_attached(context)
    )


def rollback_attachment(context: CliContextPort) -> None:
    attachment_plan = plan(context)
    if attachment_plan is None:
        return
    restore_attachment(
        context,
        attachment_plan,
        ATTACH_PLAN_PARAMETER,
    )
