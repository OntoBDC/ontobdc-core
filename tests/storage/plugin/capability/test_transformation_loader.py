from ontobdc.shared.adapter.loader import CapabilityLoader


TRANSFORMATION_CAPABILITY_IDS = [
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_datapackage_updated"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_attached"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_inspected"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_metadata_attached"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "context_attached"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "datasets_attached"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "identity_resolved"
    ),
    (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "storage_index_attached"
    ),
]


def test_storage_transformation_capabilities_are_discoverable() -> None:
    loader = CapabilityLoader()

    for capability_id in TRANSFORMATION_CAPABILITY_IDS:
        assert loader.get(capability_id) is not None, capability_id
