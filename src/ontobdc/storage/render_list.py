import sys
import json
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

def main():
    # Lê os dados do stdin (pipe ou redirecionamento)
    input_data = sys.stdin.read().strip()
    
    if not input_data or input_data == "[]":
        return
        
    try:
        # Pega a parte do json (caso haja prints de log antes, pega a partir do primeiro colchete)
        start_idx = input_data.find("[")
        if start_idx != -1:
            json_str = input_data[start_idx:]
        else:
            json_str = input_data
            
        data = json.loads(json_str)
    except json.JSONDecodeError:
        print("Erro ao decodificar JSON da saída do list.py")
        print("Input recebido:", input_data)
        return
        
    console = Console()
    
    for item in data:
        container_id = item.get("@id", "N/A")
        container_title = item.get("title", "")
        container_location = item.get("location", "").split('file://')[-1]
        
        # Criação do cabeçalho da seção (Container)
        header_text = Text()
        header_text.append("Container ID: ", style="bold cyan")
        header_text.append(f"{container_id}\n", style="white")
        header_text.append("Title: ", style="bold cyan")
        header_text.append(f"{container_title}\n", style="white")
        header_text.append("Location: ", style="bold cyan")
        header_text.append(f"{container_location}\n", style="white")
        
        datasets = item.get("dataset", [])
        
        # Tabela de Datasets do Container atual
        table = Table(show_lines=True, title_style="bold green", expand=True)
        
        # overflow="fold" garante que as informações nunca sejam truncadas (com "...")
        table.add_column("Dataset ID", style="green", overflow="fold")
        table.add_column("Title", style="white", overflow="fold")
        table.add_column("Location", style="blue", overflow="fold")
        
        if not datasets:
            table.add_row("-", "No datasets found", "-")
        else:
            for dataset in datasets:
                dataset_id = dataset.get("@id", "N/A")
                dataset_title = dataset.get("title", "")
                dataset_location = dataset.get("location", "").split('file://')[-1]
                dataset_location = f"[~]{dataset_location.split(container_location)[-1]}"
                
                table.add_row(
                    dataset_id, 
                    dataset_title, 
                    dataset_location
                )
                
        # Agrupa o texto e a tabela e os coloca dentro de um único painel cinza
        panel_content = Group(header_text, table)
        console.print(Panel(panel_content, expand=True, border_style="grey50"))
        console.print() # Espaço entre os containers

if __name__ == "__main__":
    main()
