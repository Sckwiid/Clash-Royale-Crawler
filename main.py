"""
main.py — CLI Clash Royale Crawler.

Usage:
  python main.py init-db   Initialise le schema Turso
  python main.py crawl     Lance le crawler
  python main.py stats     Affiche les statistiques
"""
from __future__ import annotations
import asyncio
import sys

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def usage() -> None:
    console.print(
        "\n[bold cyan]Clash Royale Crawler[/bold cyan]\n\n"
        "  [green]python main.py init-db[/green]   Initialise le schema\n"
        "  [green]python main.py crawl[/green]     Lance le crawler\n"
        "  [green]python main.py stats[/green]     Statistiques\n"
    )


async def cmd_init_db() -> None:
    from src.db import Database
    db = Database()
    await db.connect()
    await db.init_schema()
    await db.close()
    console.print("[bold green]Base de donnees initialisee.[/bold green]")


async def cmd_crawl() -> None:
    from src.crawler import Crawler
    await Crawler().run()


async def cmd_stats() -> None:
    from src.db import Database
    db = Database()
    await db.connect()
    t = Table(title="Statistiques Clash Royale Crawler", box=box.ROUNDED)
    t.add_column("Metrique", style="cyan", min_width=28)
    t.add_column("Valeur", style="bold white")
    t.add_row("Total joueurs",            str(await db.count_players()))
    t.add_row("Total clans",              str(await db.count_clans()))
    t.add_row("Total batailles",          str(await db.count_battles()))
    t.add_row("Queue joueurs en attente", str(await db.count_player_queue()))
    t.add_row("Queue clans en attente",   str(await db.count_clan_queue()))
    console.print(t)
    bd = await db.activity_breakdown()
    if bd:
        t2 = Table(title="Repartition activite", box=box.SIMPLE)
        t2.add_column("Status", style="yellow")
        t2.add_column("Joueurs")
        for s in ["hot", "active", "warm", "cold", "unknown"]:
            t2.add_row(s, str(bd.get(s, 0)))
        console.print(t2)
    await db.close()


COMMANDS = {"init-db": cmd_init_db, "crawl": cmd_crawl, "stats": cmd_stats}


def main() -> None:
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        console.print(f"[red]Commande inconnue: {cmd}[/red]")
        usage()
        sys.exit(1)
    try:
        asyncio.run(COMMANDS[cmd]())
    except EnvironmentError as exc:
        console.print(f"[bold red]Erreur de configuration:[/bold red] {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrompu.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
