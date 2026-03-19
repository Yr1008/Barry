#!/usr/bin/env python3
"""
Barry — Your Personal AI Assistant
====================================
Usage:
  python main.py              # Start web server + scheduler
  python main.py chat         # Interactive CLI chat
  python main.py briefing     # Generate morning briefing
  python main.py todos        # Show prioritized todos
  python main.py poll         # Poll all connectors now
  python main.py status       # Show system status
  python main.py setup        # First-time setup wizard
"""
from __future__ import annotations

import asyncio
import sys
import logging
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "server"

    setup_logging()

    if command == "server":
        run_server()
    elif command == "chat":
        asyncio.run(run_cli_chat())
    elif command == "briefing":
        asyncio.run(run_briefing())
    elif command == "todos":
        asyncio.run(run_todos())
    elif command == "poll":
        asyncio.run(run_poll())
    elif command == "status":
        asyncio.run(run_status())
    elif command == "setup":
        asyncio.run(run_setup())
    elif command == "iphone-setup":
        asyncio.run(run_iphone_setup())
    else:
        print(__doc__)
        sys.exit(1)


def run_server():
    """Start the FastAPI server with scheduler."""
    import uvicorn
    from api.server import create_app

    print("""
╔══════════════════════════════════════╗
║         ⚡ BARRY AI ASSISTANT ⚡        ║
║    Your Personal Jarvis — Starting   ║
╚══════════════════════════════════════╝
""")

    try:
        from config import get_config
        config = get_config()
        print(f"  Owner:    {config.owner_name}")
        print(f"  Timezone: {config.timezone}")
        print(f"  Briefing: {config.briefing_time} daily")
        print(f"  Polling:  every {config.poll_interval_minutes} min")
        print(f"  Dashboard: http://localhost:{config.api_port}")
        print()

        app = create_app()
        uvicorn.run(app, host=config.api_host, port=config.api_port, log_level="warning")
    except Exception as e:
        print(f"Error starting server: {e}")
        print("Make sure you've copied .env.example to .env and filled in your API key.")
        sys.exit(1)


async def run_cli_chat():
    """Interactive CLI chat with Barry."""
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.styles import Style

        console = Console()
        session = PromptSession(
            history=FileHistory(str(Path.home() / ".barry_history")),
            style=Style.from_dict({"prompt": "ansicyan bold"}),
        )

        console.print(Panel.fit(
            "[bold cyan]⚡ Barry — AI Assistant[/bold cyan]\n"
            "[dim]Type your message and press Enter. 'exit' to quit.[/dim]",
            border_style="cyan",
        ))

        from barry import Barry
        barry = Barry()

        # Initial poll
        console.print("[dim]Connecting to your services...[/dim]")
        try:
            await barry.poll_all()
            status = barry.get_status()
            console.print(
                f"[green]✓[/green] Connected | "
                f"[yellow]{status['memory']['todos']}[/yellow] todos | "
                f"[blue]{len(barry._last_events)}[/blue] events | "
                f"[red]{len(barry._last_emails)}[/red] emails\n"
            )
        except Exception as e:
            console.print(f"[yellow]⚠ Could not fetch all data: {e}[/yellow]\n")

        while True:
            try:
                user_input = await session.prompt_async("You > ")
                if not user_input.strip():
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    console.print("[cyan]Barry: Goodbye! 👋[/cyan]")
                    break

                console.print("[dim cyan]Barry > [/dim cyan]", end="")

                # Stream response
                response_text = ""
                async for chunk in await barry.chat(user_input, stream=True):
                    console.print(chunk, end="")
                    response_text += chunk
                console.print()  # New line after response
                console.print()

            except KeyboardInterrupt:
                console.print("\n[cyan]Barry: Type 'exit' to quit.[/cyan]")
                continue
            except EOFError:
                break

    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install rich prompt-toolkit")
        # Fallback to simple CLI
        await _simple_cli_chat()


async def _simple_cli_chat():
    """Simple fallback CLI without rich/prompt_toolkit."""
    from barry import Barry
    barry = Barry()

    print("Barry > Ready! (type 'exit' to quit)")
    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            print("Barry > ", end="", flush=True)
            async for chunk in await barry.chat(user_input, stream=True):
                print(chunk, end="", flush=True)
            print("\n")
        except KeyboardInterrupt:
            break


async def run_briefing():
    """Generate and print the daily briefing."""
    from barry import Barry
    barry = Barry()

    print("Generating briefing...")
    await barry.poll_all()
    briefing = await barry.generate_daily_briefing()
    print("\n" + briefing)


async def run_todos():
    """Show prioritized todos."""
    from barry import Barry
    barry = Barry()

    await barry.poll_all()
    result = await barry.get_prioritized_todos()
    print("\n" + result)


async def run_poll():
    """Poll all connectors and show results."""
    from barry import Barry
    barry = Barry()

    print("Polling all connectors...")
    results = await barry.poll_all()
    print("\nResults:")
    for source, info in results.get("poll_results", {}).items():
        print(f"  {source}: {info}")

    new_items = results.get("new_items", {})
    if new_items:
        print("\nNew items found:")
        for source, items in new_items.items():
            print(f"  {source}: {len(items)} new")
    else:
        print("\nNo new items.")


async def run_status():
    """Show system status."""
    from barry import Barry
    barry = Barry()

    status = barry.get_status()
    print(f"\n⚡ {status['name']} Status")
    print(f"Owner: {status['owner']}")
    print(f"Timezone: {status['timezone']}")
    print("\nConnectors:")
    for conn, enabled in status["connectors"].items():
        icon = "✅" if enabled else "❌"
        print(f"  {icon} {conn.replace('_', ' ').title()}")
    print("\nMemory:")
    for key, val in status["memory"].items():
        print(f"  {key}: {val}")


async def run_setup():
    """First-time setup wizard."""
    print("""
╔══════════════════════════════════════╗
║         BARRY SETUP WIZARD           ║
╚══════════════════════════════════════╝

Welcome! Let's set up Barry.

Step 1: Create your .env file
  cp .env.example .env

Step 2: Add your API keys to .env:
  - ANTHROPIC_API_KEY (required) — get from console.anthropic.com
  - BARRY_OWNER_NAME — your name
  - BARRY_TIMEZONE — your timezone (e.g., America/New_York)

Step 3: Connect your services:
  Gmail/Calendar: Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    → Start Barry server, then visit http://localhost:8000/auth/google

  iCloud: Set ICLOUD_EMAIL and ICLOUD_PASSWORD (app-specific password)
    → Generate at appleid.apple.com → App-Specific Passwords

  WhatsApp: Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
    → Sign up at twilio.com, enable WhatsApp Sandbox

  iPhone: Set SHORTCUTS_WEBHOOK_SECRET
    → Visit http://localhost:8000/iphone/setup for Shortcuts setup

Step 4: Start Barry:
  python main.py           # Web server
  python main.py chat      # CLI chat
""")


async def run_iphone_setup():
    """Show iPhone/Mac setup guide."""
    from barry import Barry
    barry = Barry()
    print(barry.iphone.get_shortcuts_setup_guide())


if __name__ == "__main__":
    main()
