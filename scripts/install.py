import os
import subprocess
import sys
from rich.console import Console
from rich.prompt import Confirm, Prompt

console = Console()

def run_command(command, description=None, env=None):
    if description:
        console.print(f"[bold blue]{description}...[/bold blue]")
    try:
        # Merge current env with provided env
        current_env = os.environ.copy()
        if env:
            current_env.update(env)
        subprocess.run(command, shell=True, check=True, env=current_env)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running command: {e}[/bold red]")
        return False

def is_command_available(command):
    try:
        subprocess.run(f"command -v {command}", shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def setup_env():
    """Ensure essential environment variables are set."""
    env_updates = {}
    
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        console.print("[yellow]Warning: No Google API credentials found.[/yellow]")
        api_key = Prompt.ask("Enter your GOOGLE_API_KEY (optional, press Enter to skip)")
        if api_key:
            env_updates["GOOGLE_API_KEY"] = api_key
            # Persist to .env for future use
            with open(".env", "a") as f:
                f.write(f"\nGOOGLE_API_KEY={api_key}\n")
    
    # Ensure QDRANT_URL points to a local directory for embedded mode
    if not os.getenv("QDRANT_URL"):
        # Default to a directory in the user's home or project root
        qdrant_path = os.path.abspath("qdrant_storage")
        env_updates["QDRANT_URL"] = qdrant_path
        with open(".env", "a") as f:
            f.write(f"\nQDRANT_URL={qdrant_path}\n")
            
    return env_updates

def main():
    console.print("[bold green]Welcome to qdoc All-in-One Installer![/bold green]")
    console.print("This will set up qdoc with an embedded database (no Docker needed).")
    
    # 1. Setup Environment
    env_vars = setup_env()
    
    # 2. Install CLI
    if Confirm.ask("Do you want to install 'qdoc' CLI globally using uv?"):
        run_command("uv tool install --force .", "Installing qdoc CLI")
    
    # 3. Install Playwright
    if Confirm.ask("Do you want to install Playwright browser dependencies?"):
        run_command("uv run playwright install chromium", "Installing Playwright chromium")
        
    # Get absolute path to qdoc for MCP registration
    qdoc_path = subprocess.check_output("which qdoc || echo qdoc", shell=True).decode().strip()
    
    # 4. Claude Code MCP
    if is_command_available("claude"):
        if Confirm.ask("Do you want to install qdoc MCP server for Claude Code?"):
            run_command(f"claude mcp add qdoc -- {qdoc_path} serve", "Adding qdoc to Claude Code", env=env_vars)
    else:
        console.print("[yellow]Claude Code ('claude') not found in PATH. Skipping Claude MCP installation.[/yellow]")
        
    # 5. Gemini CLI MCP
    if is_command_available("gemini"):
        if Confirm.ask("Do you want to install qdoc MCP server for Gemini CLI?"):
            run_command(f"gemini mcp add qdoc -- {qdoc_path} serve", "Adding qdoc to Gemini CLI", env=env_vars)
    else:
        console.print("[yellow]Gemini CLI ('gemini') not found in PATH. Skipping Gemini MCP installation.[/yellow]")
        
    console.print("\n[bold green]Installation process finished![/bold green]")
    console.print("[blue]Tip: If you haven't yet, make sure your terminal has the GOOGLE_API_KEY exported.[/blue]")

if __name__ == "__main__":
    main()
