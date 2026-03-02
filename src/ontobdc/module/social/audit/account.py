
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from ontobdc.core.domain.port.verification import VerificationStrategyPort
from ontobdc.run.core.capability import CapabilityExecutor, CapabilityRegistry


class ValidWhatsappAccount(VerificationStrategyPort):
    """
    Checks if the provided WhatsApp account corresponds to a valid export folder.
    Expects input to be the account name or number (e.g., "+55 28 99976-2610").
    """

    def __call__(self, input_key: str, input_value: Any, inputs: Dict[str, Any]) -> bool:
        return self.verify(input_key, input_value, inputs)

    def verify(self, input_key: str, input_value: Any, inputs: Dict[str, Any]) -> bool:
        if not isinstance(input_value, str) or not input_value:
            return False
        
        accounts = self._get_all(inputs)
        return input_value in accounts

    def get_account(self, input_value: str, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._get_all(inputs).get(input_value)

    def _get_all(self, inputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        try:
            cap_cls = CapabilityRegistry.get("org.ontobdc.domain.social.capability.list_whatsapp_accounts")
            if not cap_cls:
                return {}

            capability = cap_cls()
            result = CapabilityExecutor().execute(
                capability=capability,
                inputs=inputs,
            )
            content = result.get("org.ontobdc.domain.social.account.list.content", [])
            # Convert list to dict keyed by ID
            return {item["id"]: item for item in content}
        except Exception:
            # If capability fails or not found, return empty dict
            return {}
