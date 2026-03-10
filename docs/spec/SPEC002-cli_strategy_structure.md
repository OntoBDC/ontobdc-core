---
code: SPEC002
title: CLI Strategy Structure Specification
status: Accepted
author: Elias M. P. Junior
date: 2026-02-26
tags: architecture, cli, adapter, strategy
---

# CLI Strategy Structure Specification

This document defines the standard structure and location for implementing **CLI Strategies** in the OntoBDC architecture. A CLI Strategy acts as an adapter between the Command Line Interface (CLI) and the domain logic (Capabilities/Actions), handling argument parsing, input mapping, and output rendering.

## 1. File Location
CLI Strategies must be placed within the `module/<domain>/adapter/strategy/` directory.

- **Naming Convention**: `cli_<entity>.py` or `cli_<action>.py`
- **Example**: `ontobdc/module/resource/adapter/strategy/cli_account.py`
- **Example**: `ontobdc/module/social/adapter/strategy/cli_whatsapp.py`

Strategies should NOT be placed directly in `module/<domain>/adapter/cli_strategy.py`. The `adapter` folder should contain sub-packages for better organization.

## 2. Class Definition
A CLI Strategy is a Python class that does not inherit from a specific base class but must implement a specific interface (implicit or explicit protocol).

```python
from typing import Any, Dict, Optional
from rich.console import Console
from ontobdc.run.core.capability import Capability  # or Action
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort

class MyFeatureCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        # Initialize dependencies, typically the repository
        self.repository: Optional[DocumentRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        """
        Configures argparse arguments for this strategy.
        """
        parser.add_argument(
            "--my-flag",
            dest="my_flag",
            required=False,
            help="Description of the flag.",
        )

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        """
        Executes the strategy: maps args to inputs, validates, executes capability, and renders result.
        """
        inputs: Dict[str, Any] = {
            "repository": self.repository,
            "my_key": args.my_flag,
        }

        # 1. Validation (optional but recommended to use METADATA schema)
        # ...

        # 2. Execute
        try:
            result = capability.execute(inputs)
            self.render(console, result)
        except Exception as e:
            console.print(f"[red]Execution Error:[/red] {e}")

    def render(self, console: Console, result: Any) -> None:
        """
        Renders the execution result to the console (e.g., using Rich tables).
        """
        # ...
```

## 3. High-Level Abstraction
Strategies should be as high-level as possible and reusable where appropriate.
- A single strategy file (e.g., `cli_account.py`) can contain strategies related to a specific entity (e.g., `ListAccountsCliStrategy`).
- Strategies should be decoupled from the specific Capability implementation details where possible, focusing on the *interaction* (CLI args -> Input Dict -> Output View).

## 4. Usage in Capabilities/Actions
Capabilities and Actions refer to their default strategy via the `get_default_cli_strategy` method.

```python
    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        from ontobdc.module.domain.adapter.strategy.cli_feature import MyFeatureCliStrategy
        return MyFeatureCliStrategy(**kwargs)
```

## 5. Architectural Constraints
1.  **No Business Logic**: Strategies must NOT contain business logic. They only map inputs and render outputs.
2.  **No Direct Filesystem Access**: Strategies must use Repositories passed via `__init__`, never accessing files directly.
