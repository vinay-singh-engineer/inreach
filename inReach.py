#!/usr/bin/env python3
"""
inReach.py — CLI network connectivity checker

Examples:
    python inReach.py --destination google.com --port 443
    python inReach.py --source myhost --destination google.com --port 443
    python inReach.py --sourceFile /path/to/hosts --destination google.com --port 443
    python inReach.py --source host1 --sourceFile /path/to/hosts --destination google.com
    python inReach.py --sourceFile /path/to/hosts --destination google.com --parallel
    python inReach.py --sourceFile /path/to/hosts --destination google.com --parallel --workers 8
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.live import Live

from connectivity import _clean_output, check_local, check_remote  # noqa: F401

console = Console()

_VERSION = (Path(__file__).parent / "VERSION").read_text().strip()


def parse_hosts_file(path: str) -> list[str]:
    p = Path(path)
    if not p.is_file():
        console.print(f"[red]✘  File not found:[/red] {path}")
        sys.exit(1)
    hosts = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        host = line.split()[0]
        if "=" not in host and ":" not in host:
            hosts.append(host)
    return hosts


def run_check(source: str, dest: str, port: int) -> tuple[bool, str]:
    if source in ("localhost", "127.0.0.1"):
        return check_local(dest, port)
    return check_remote(source, dest, port)


def print_header(dest: str, port: int):
    console.print()
    console.print(Panel.fit(
        f"[bold white]inReach[/bold white]  [dim]v{_VERSION}[/dim]\n"
        f"[dim]Destination:[/dim] [cyan]{dest}[/cyan]   "
        f"[dim]Port:[/dim] [cyan]{port}[/cyan]",
        border_style="bright_black",
        padding=(0, 2),
    ))
    console.print()


_COL_DEST   = 26
_COL_STATUS = 15


class _CheckLine:
    """Single animated line matching the result row layout: spinner | source | dest:port | checking…"""

    def __init__(self, source: str, dest: str, port: int, col_src: int, idx: int = 0, total: int = 0):
        self._spinner  = Spinner("dots")
        self._source   = source
        self._destport = f"{dest}:{port}"
        self._col_src  = col_src
        self._progress = f" ({idx}/{total})" if total > 1 else ""

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        frame = self._spinner.render(time.monotonic())
        line  = Text()
        line.append(" ")
        line.append_text(frame)
        line.append(f"   {self._source:<{self._col_src}} ", style="dim")
        line.append(f"{self._destport:<{_COL_DEST}} ", style="dim")
        line.append(f"checking…{self._progress}", style="dim italic")
        yield line


def print_result_header(col_src: int):
    console.print(
        f"  [bold bright_black]    {'Source':<{col_src}} {'Destination':<{_COL_DEST}} {'Status':<{_COL_STATUS}} Detail[/bold bright_black]"
    )
    console.print(f"  [bright_black]{'─' * (4 + col_src + _COL_DEST + _COL_STATUS + 10)}[/bright_black]")


def print_result_row(source: str, dest: str, port: int, ok: bool, msg: str, col_src: int):
    ic          = "[green]✔[/green]" if ok else "[red]✘[/red]"
    dest_port   = f"{dest}:{port}"
    status_text = f"{'● REACHABLE':<{_COL_STATUS}}" if ok else f"{'● UNREACHABLE':<{_COL_STATUS}}"
    status_fmt  = f"[bold green]{status_text}[/bold green]" if ok else f"[bold red]{status_text}[/bold red]"
    console.print(
        f" {ic}   {source:<{col_src}} [dim]{dest_port:<{_COL_DEST}}[/dim] {status_fmt} [dim]{msg}[/dim]"
    )


def single_mode(source: str, dest: str, port: int):
    print_header(dest, port)
    col_src = len(source)

    print_result_header(col_src)

    with Live(_CheckLine(source, dest, port, col_src), console=console, refresh_per_second=12, transient=True):
        ok, msg = run_check(source, dest, port)

    print_result_row(source, dest, port, ok, msg, col_src)
    console.print()


def multi_mode(pairs: list[tuple[str, str]], port: int, parallel: bool = False, workers: int = 5):
    dests = list(dict.fromkeys(dst for _, dst in pairs))
    dest_str = ", ".join(dests)

    console.print()
    console.print(Panel.fit(
        f"[bold white]inReach[/bold white]  [dim]v{_VERSION}[/dim]\n"
        f"[dim]Destination:[/dim] [cyan]{dest_str}[/cyan]   "
        f"[dim]Port:[/dim] [cyan]{port}[/cyan]",
        border_style="bright_black",
        padding=(0, 2),
    ))
    console.print()

    results = []
    total   = len(pairs)
    col_src = max(len(src) for src, _ in pairs)

    print_result_header(col_src)

    if parallel:
        with ThreadPoolExecutor(max_workers=min(total, workers)) as executor:
            future_to_pair = {executor.submit(run_check, src, dst, port): (src, dst) for src, dst in pairs}
            for future in as_completed(future_to_pair):
                src, dst = future_to_pair[future]
                try:
                    ok, msg = future.result()
                except Exception as e:
                    ok, msg = False, str(e)
                results.append((src, dst, ok, msg))
                print_result_row(src, dst, port, ok, msg, col_src)
    else:
        for i, (source, dest) in enumerate(pairs, 1):
            with Live(_CheckLine(source, dest, port, col_src, i, total), console=console, refresh_per_second=12, transient=True):
                ok, msg = run_check(source, dest, port)
            results.append((source, dest, ok, msg))
            print_result_row(source, dest, port, ok, msg, col_src)

    # Summary
    passed = sum(1 for *_, ok, _ in results if ok)
    failed = total - passed

    console.print()
    summary = Table(box=None, show_header=False, pad_edge=False)
    summary.add_column(width=20)
    summary.add_column()
    summary.add_row("[dim]Total checked[/dim]", f"[white]{total}[/white]")
    summary.add_row("[dim]Reachable[/dim]",     f"[green]{passed}[/green]")
    summary.add_row("[dim]Unreachable[/dim]",   f"[red]{failed}[/red]" if failed else f"[dim]{failed}[/dim]")

    console.print(Panel.fit(summary, title="[bold blue]Summary[/bold blue]", border_style="blue", padding=(0, 2)))
    console.print()

    sys.exit(0 if failed == 0 else 1)


def print_help():
    console.print()
    console.print(Panel.fit(
        f"[bold white]inReach[/bold white]  [dim]v{_VERSION}[/dim]\n"
        f"[dim]Check TCP connectivity from source(s) to a destination:port[/dim]",
        border_style="bright_black",
        padding=(0, 2),
    ))
    console.print()

    # Usage
    console.print("  [bold bright_black]Usage[/bold bright_black]")
    console.print("  [dim]python inReach.py --destination [/dim][cyan]<host>[/cyan] [dim]\\[options][/dim]")
    console.print()

    # Arguments table
    args_table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    args_table.add_column(style="cyan",       min_width=22)
    args_table.add_column(style="white",      min_width=30)
    args_table.add_column(style="dim")

    args_table.add_row("-d, --destination",  "Destination host or IP",    "[red]required[/red]")
    args_table.add_row("-s, --source",       "Source host",               "default: localhost")
    args_table.add_row("-p, --port",         "Port number",               "default: 443")
    args_table.add_row("-f, --sourceFile",   "Hosts file (one per line or Ansible inventory)", "optional")
    args_table.add_row("-w, --workers",      "Max concurrent checks",     "default: 5")
    args_table.add_row("    --parallel",     "Run checks in parallel",    "default: sequential")
    args_table.add_row("-v, --version",      "Show version and exit",     "")
    args_table.add_row("-h, --help",         "Show this help message",    "")

    console.print("  [bold bright_black]Arguments[/bold bright_black]")
    console.print(args_table)
    console.print()

    # Examples table
    ex_table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    ex_table.add_column(style="dim green", min_width=72)

    ex_table.add_row("python inReach.py --destination google.com --port 443")
    ex_table.add_row("python inReach.py --source myhost --destination google.com --port 443")
    ex_table.add_row("python inReach.py --sourceFile /path/to/hosts --destination google.com --port 443")
    ex_table.add_row("python inReach.py --source myhost --sourceFile /path/to/hosts --destination google.com")
    ex_table.add_row("python inReach.py --sourceFile /path/to/hosts --destination google.com --parallel")
    ex_table.add_row("python inReach.py --sourceFile /path/to/hosts --destination google.com --parallel --workers 8")

    console.print("  [bold bright_black]Examples[/bold bright_black]")
    console.print(ex_table)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        prog="inReach",
        description="Check TCP connectivity from one or more sources to a destination:port",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("--help",        "-h", action="store_true",   help="Show this help message")
    parser.add_argument("--version",     "-v", action="version",      version=f"inReach v{_VERSION}")
    parser.add_argument("--source",      "-s", default="localhost",   help="Source host (default: localhost)")
    parser.add_argument("--destination", "-d", default=None,          help="Destination host(s) — comma-separated for multiple")
    parser.add_argument("--port",        "-p", type=int, default=443, help="Port (default: 443)")
    parser.add_argument("--sourceFile",  "-f", default=None,          help="Path to hosts file (one host per line or Ansible inventory)")
    parser.add_argument("--workers",     "-w", type=int, default=5,   help="Max concurrent checks (default: 5)")
    parser.add_argument("--parallel",         action="store_true",    help="Run checks in parallel (default: sequential)")

    args = parser.parse_args()

    if args.help or args.destination is None:
        print_help()
        sys.exit(0)

    if not (1 <= args.port <= 65535):
        console.print("[red]✘  Port must be between 1 and 65535.[/red]")
        sys.exit(1)

    sources = []
    if args.sourceFile:
        sources = parse_hosts_file(args.sourceFile)
        if not sources:
            console.print("[red]No hosts found in file.[/red]")
            sys.exit(1)
    if args.source != "localhost" or not sources:
        if args.source not in sources:
            sources.insert(0, args.source)

    dests = [d.strip() for d in args.destination.split(",") if d.strip()]
    pairs = [(src, dst) for src in sources for dst in dests]

    if len(pairs) == 1:
        single_mode(pairs[0][0], pairs[0][1], args.port)
    else:
        multi_mode(pairs, args.port, parallel=args.parallel, workers=args.workers)


if __name__ == "__main__":
    main()
