from rich.console import Console
from typing import List, Dict, Any, Optional

class SimpleMenuSelector:
    def __init__(self, console=None):
        self.console = console or Console()

    def select_option(self, options, title="Select Option:"):
        self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        
        # Display options
        for i, opt in enumerate(options, 1):
            label = opt["label"] if isinstance(opt, dict) else opt
            self.console.print(f"  [cyan]{i}][/cyan] {label}")
            
        self.console.print("\n  [dim]0][/dim] Cancel")
        
        while True:
            try:
                choice = self.console.input("\n[bold]Enter choice:[/bold] ")
                if not choice.strip():
                    continue
                    
                idx = int(choice)
                if idx == 0:
                    return None
                
                if 1 <= idx <= len(options):
                    selected = options[idx - 1]
                    # Return just the value if it's a dict, or the option itself
                    return selected["value"] if isinstance(selected, dict) else selected
                
                self.console.print("[red]Invalid choice. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
