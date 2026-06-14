
import os
from ontobdc.shared.adapter.machine import LocalStatechartRepository


class IntentLocalStatechartRepository(LocalStatechartRepository):
    """
    Repository to load the Sismic Statechart from the local filesystem.
    """
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "domain", "machine", "capability_intent_resolution.yaml")

        super().__init__(filepath)