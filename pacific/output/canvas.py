"""PACIFIC — Canvas: execute code blocks from AI responses to produce outputs."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from pacific.config import load_config

console = Console()


def extract_code_blocks(text: str) -> list:
    """Extract fenced code blocks from markdown text.

    Returns list of dicts: [{'lang': 'python', 'code': '...'}]
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    blocks = []
    for lang, code in matches:
        blocks.append({
            "lang": lang.lower() or "python",
            "code": code.strip(),
        })
    return blocks


def execute_code_block(
    code: str,
    lang: str = "python",
    output_dir: Optional[str] = None,
    auto_confirm: bool = False,
) -> Optional[str]:
    """Execute a code block and capture output / generated files.

    Args:
        code: The source code to execute.
        lang: Language (currently only 'python' supported).
        output_dir: Working directory for execution.
        auto_confirm: If False, prompt user before executing.

    Returns:
        stdout/stderr of the execution, or None if cancelled.
    """
    if lang != "python":
        console.print(f"[yellow]⚠ Only Python execution is supported (got: {lang})[/yellow]")
        return None

    # Show preview
    console.print(Panel(
        Syntax(code, "python", theme="monokai", line_numbers=True),
        title="[bold yellow]Code to Execute[/bold yellow]",
        border_style="yellow",
    ))

    if not auto_confirm:
        console.print("[bold yellow]Execute this code?[/bold yellow] [dim](y/N)[/dim] ", end="")
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if answer not in ("y", "yes"):
            console.print("[dim]Skipped.[/dim]")
            return None

    cfg = load_config()
    if not output_dir:
        output_dir = cfg.get("output_dir", str(Path.home() / ".pacific" / "outputs"))
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Write to temp file and execute
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir=output_dir, delete=False
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=output_dir,
        )

        if result.stdout:
            console.print(Panel(result.stdout.strip(), title="[green]Output[/green]", border_style="green"))
        if result.stderr:
            console.print(Panel(result.stderr.strip(), title="[red]Errors[/red]", border_style="red"))

        return result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Execution timed out (120s limit)[/red]")
        return None
    except Exception as e:
        console.print(f"[red]✗ Execution error: {e}[/red]")
        return None
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def auto_execute_response(text: str, auto_confirm: bool = False) -> list:
    """Extract and optionally execute all Python code blocks from a response.

    Returns list of execution results.
    """
    blocks = extract_code_blocks(text)
    if not blocks:
        return []

    python_blocks = [b for b in blocks if b["lang"] == "python"]
    if not python_blocks:
        return []

    console.print(f"\n[bold cyan]Found {len(python_blocks)} executable code block(s)[/bold cyan]")
    results = []
    for i, block in enumerate(python_blocks, 1):
        console.print(f"\n[bold]Block {i}/{len(python_blocks)}:[/bold]")
        result = execute_code_block(block["code"], auto_confirm=auto_confirm)
        results.append(result)

    return results
