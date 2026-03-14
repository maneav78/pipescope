from urllib.parse import urljoin
import requests
from rich.console import Console
import concurrent.futures
from pathlib import Path

console = Console()

def run_web_recon(url: str, wordlist_path: str = None, wordlist_name: str = "common", threads: int = 10):
    console.print(f"[bold]Starting web recon on {url}[/bold]")
    
    if wordlist_path:
        wordlist_file = Path(wordlist_path)
    else:
        wordlist_file = Path(__file__).parent.parent / "wordlists" / f"{wordlist_name}.txt"

    if not wordlist_file.exists():
        console.print(f"[red]Wordlist file not found at: {wordlist_file}[/red]")
        return []

    with open(wordlist_file, "r") as f:
        words = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    found_paths = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        future_to_path = {executor.submit(check_path, url, word): word for word in words}
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                if result:
                    found_paths.append(result)
            except Exception as exc:
                console.print(f"[red]{path} generated an exception: {exc}[/red]")
    
    return found_paths
