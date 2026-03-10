from rich.console import Console
from typing import List, Dict, Any, Optional

class SimpleMenuSelector:
    def __init__(self, console=None):
        self.console = console or Console()

    def select_option(self, options, title="Select Option:", print_menu=True):
        if print_menu:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
            self.console.print("")

            # Display options
            for i, opt in enumerate(options, 1):
                label = opt["label"] if isinstance(opt, dict) else opt
                self.console.print(f"  [cyan]{i}][/cyan] {label}")

        while True:
            try:
                choice = self.console.input("\n[bold]Enter choice:[/bold] ")
                
                # Check for ESC character (ASCII 27) if terminal sends it (unlikely in line mode without raw)
                if choice == '\x1b':
                    return None
                
                # Also handle if user types '0' or 'ESC' or 'exit'
                if choice.strip().upper() in ["0", "ESC", "EXIT", "Q"]:
                    return None

                idx = int(choice)

                if 1 <= idx <= len(options):
                    selected = options[idx - 1]
                    # Return just the value if it's a dict, or the option itself
                    if isinstance(selected, dict) and "value" in selected:
                        return selected["value"]
                    return selected

                self.console.print("[red]Invalid choice. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
