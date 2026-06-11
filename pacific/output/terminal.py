"""PACIFIC — Rich terminal rendering: banners, panels, tables."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns

from pacific import __version__, __app__, __tagline__

console = Console()

LOGO = r"""
[bold cyan]
    ██████╗  █████╗  ██████╗██╗███████╗██╗ ██████╗
    ██╔══██╗██╔══██╗██╔════╝██║██╔════╝██║██╔════╝
    ██████╔╝███████║██║     ██║█████╗  ██║██║
    ██╔═══╝ ██╔══██║██║     ██║██╔══╝  ██║██║
    ██║     ██║  ██║╚██████╗██║██║     ██║╚██████╗
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝╚═╝╚═╝     ╚═╝ ╚═════╝
[/bold cyan]"""


def print_banner():
    """Print the startup banner."""
    console.print(LOGO)
    console.print(
        f"  [bold white]{__tagline__}[/bold white]  [dim]v{__version__}[/dim]"
    )
    console.print(
        "  [dim]Powered by GRRN · pacific.grrn.io[/dim]\n"
    )


def print_separator():
    """Print a dim horizontal rule."""
    console.print("[dim]" + "─" * console.width + "[/dim]")


def print_status(label: str, value: str, style: str = "green"):
    """Print a key-value status line."""
    console.print(f"  [dim]{label}:[/dim] [bold {style}]{value}[/bold {style}]")


def print_error(msg: str):
    """Print a red error message."""
    console.print(f"  [bold red]✗[/bold red] {msg}")


def print_success(msg: str):
    """Print a green success message."""
    console.print(f"  [bold green]✓[/bold green] {msg}")


def print_table(title: str, columns: list, rows: list):
    """Print a rich table with given columns and rows."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)
