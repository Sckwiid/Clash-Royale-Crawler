"""
main.py — CLI Clash Royale Crawler.

Commandes:
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
        "  [green]python main.py init-db[/green]   Initialise le schema de la base de donnees\n"
        "  [green]python main.py crawl[/green]     Lance le crawler\n"
        "  [green]python main.py stats[/green]     Affiche les statistiques\n"
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
    crawler = Crawler()
    await crawler.run()


async def cmd_stats() -> None:
    from src.db import Database
    db = Database()
    await db.connect()

    n_p  = await db.count_players()
    n_c  = await db.count_clans()
    n_b  = await db.count_battles()
    n_pq = await db.count_player_queue()
    n_cq = await db.count_clan_queue()
    bd   = await db.activity_breakdown()

    await db.close()

    t = Table(title="Statistiques Clash Royale Crawler", box=box.ROUNDED)
    t.add_column("Metrique", style="cyan", min_width=28)
    t.add_column("Valeur", style="bold white")
    t.add_row("Total joueurs",           str(n_p))
    t.add_row("Total clans",             str(n_c))
    t.add_row("Total batailles resumees",str(n_b))
    t.add_row("Queue joueurs en attente",str(n_pq))
    t.add_row("Queue clans en attente",  str(n_cq))
    console.print(t)

    if bd:
        t2 = Table(title="Repartition par activite", box=box.SIMPLE)
        t2.add_column("Status", style="yellow")
        t2.add_column("Joueurs")
        for status in ["hot", "active", "warm", "cold", "unknown"]:
            t2.add_row(status, str(bd.get(status, 0)))
        console.print(t2)


COMMANDS = {
    "init-db": cmd_init_db,
    "crawl":   cmd_crawl,
    "stats":   cmd_stats,
}


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
