
import json
from typing import Any, Dict, List
from pathlib import Path
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort
from ontobdc.module.resource.adapter.strategy.cli_account import ListAccountsCliStrategy


class ListWhatsappAccountsCapability(Capability):
    """
    Lists configured WhatsApp accounts found in the repository.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.social.capability.list_whatsapp_accounts",
        version="0.1.0",
        name="List Configured WhatsApp Accounts",
        description="Scans the repository for WhatsApp export folders and lists available accounts.",
        author=["Elias M. P. Junior"],
        tags=["social", "whatsapp", "account", "list"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": DocumentRepositoryPort,
                    "required": True,
                    "description": "Repository instance to scan for WhatsApp folders",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.social.account.list.content": {
                    "type": "array",
                    "description": "List of WhatsApp account identifiers found",
                },
                "org.ontobdc.domain.social.account.list.count": {
                    "type": "integer",
                    "description": "Number of accounts found",
                },
            },
        },
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return ListAccountsCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repository: DocumentRepositoryPort = inputs["repository"]
        
        found_accounts = []
        
        # Check for .__ontobdc__/datapackage.json in the repository root (level 1)
        # Using repository interface instead of direct filesystem access
        dp_path_str = ".__ontobdc__/datapackage.json"
        
        dp_content = None
        if hasattr(repository, "get_json"):
             dp_content = repository.get_json(dp_path_str)
        
        if dp_content:
            resources = dp_content.get("resources", [])
            for resource in resources:
                path_str = resource.get("path", "")
                # Look for resources pointing to RO-Crate metadata
                if path_str.endswith("ro-crate-metadata.json") and ".__ontobdc__" in path_str:
                    crate_path_str = path_str
                    if crate_path_str.startswith("../"):
                        crate_path_str = crate_path_str[3:]
                    
                    # Read the RO-Crate metadata
                    if hasattr(repository, "get_json"):
                        crate_content = repository.get_json(crate_path_str)
                        if crate_content and "@graph" in crate_content:
                            graph = crate_content["@graph"]
                            for node in graph:
                                node_type = node.get("@type")
                                # Normalize type to list for checking
                                if not isinstance(node_type, list):
                                    node_type = [node_type]
                                
                                if "urn:ontobdc:social:account:WhatsappAccount" in node_type:
                                    account_id = node.get("@id")
                                    alternate_names = node.get("alternateName", [])
                                    if isinstance(alternate_names, str):
                                        alternate_names = [alternate_names]
                                        
                                    found_accounts.append({
                                        "id": account_id,
                                        "names": alternate_names,
                                        "source": crate_path_str
                                    })

        return {
            "org.ontobdc.domain.social.account.list.content": found_accounts,
            "org.ontobdc.domain.social.account.list.count": len(found_accounts),
        }
