"""Analyze actual conversation patterns to validate filtering logic."""

from collections import Counter

from rich.console import Console
from rich.table import Table

from calmlib.utils.claude_code.history import (
    _is_meaningful_message,
    _is_system_message,
    get_all_messages,
    list_conversations,
    list_projects,
)


def analyze_conversation_patterns(max_conversations: int = 100):
    """Analyze first and last user messages in conversations to understand patterns.

    Args:
        max_conversations: Maximum number of conversations to analyze
    """
    console = Console()

    # Collect statistics
    total_conversations = 0
    system_message_matches = Counter()
    filtered_as_system = []
    filtered_as_filler = []
    first_messages = []
    last_messages = []

    console.print("[cyan]Analyzing conversation patterns...[/cyan]\n")

    projects = list_projects(include_stats=False)

    for project in projects:
        conversations = list_conversations(project["name"])

        for conv in conversations[:max_conversations]:
            total_conversations += 1

            # Get all messages for this conversation
            messages = get_all_messages(project["name"], conv["id"])

            # Find first and last user messages
            user_messages = [
                msg.get("message", {}).get("content", "")
                for msg in messages
                if msg.get("message", {}).get("role") == "user"
                and isinstance(msg.get("message", {}).get("content", ""), str)
            ]

            if not user_messages:
                continue

            first_msg = user_messages[0]
            last_msg = user_messages[-1]

            first_messages.append(
                (first_msg[:200], conv["id"][:8], project["display_name"])
            )
            last_messages.append(
                (last_msg[:200], conv["id"][:8], project["display_name"])
            )

            # Check if first message would be filtered
            if _is_system_message(first_msg):
                filtered_as_system.append(
                    (first_msg[:200], conv["id"][:8], project["display_name"])
                )

                # Track which pattern matched
                content_lower = first_msg.lower().strip()
                patterns = [
                    "caveat:",
                    "<system",
                    "<command",
                    "the messages below were generated",
                    "context for this conversation",
                    "you are claude",
                    "you are an ai assistant",
                ]
                for pattern in patterns:
                    if pattern in content_lower:
                        system_message_matches[pattern] += 1

            elif not _is_meaningful_message(first_msg):
                filtered_as_filler.append(
                    (first_msg[:200], conv["id"][:8], project["display_name"])
                )

    # Print statistics
    console.print(f"[bold]Total conversations analyzed:[/bold] {total_conversations}\n")

    console.print(
        f"[yellow]Messages filtered as system:[/yellow] {len(filtered_as_system)} ({len(filtered_as_system) / total_conversations * 100:.1f}%)"
    )
    console.print(
        f"[yellow]Messages filtered as filler:[/yellow] {len(filtered_as_filler)} ({len(filtered_as_filler) / total_conversations * 100:.1f}%)\n"
    )

    # Pattern match statistics
    if system_message_matches:
        console.print("[bold cyan]System message pattern matches:[/bold cyan]")
        for pattern, count in system_message_matches.most_common():
            console.print(f"  • '{pattern}': {count} matches")
        console.print()

    # Show examples of filtered messages
    if filtered_as_system:
        console.print("[bold red]Examples of messages filtered as SYSTEM:[/bold red]")
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Message", style="dim", no_wrap=False)
        table.add_column("Conv ID", style="cyan", width=10)
        table.add_column("Project", style="green", width=15)

        for msg, conv_id, project in filtered_as_system[:10]:
            table.add_row(msg[:150], conv_id, project)

        console.print(table)
        console.print()

    if filtered_as_filler:
        console.print(
            "[bold yellow]Examples of messages filtered as FILLER:[/bold yellow]"
        )
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Message", style="dim", no_wrap=False)
        table.add_column("Conv ID", style="cyan", width=10)
        table.add_column("Project", style="green", width=15)

        for msg, conv_id, project in filtered_as_filler[:10]:
            table.add_row(msg[:150], conv_id, project)

        console.print(table)
        console.print()

    # Show sample of first messages that PASSED filters
    passed_filter = [
        (msg, cid, proj)
        for msg, cid, proj in first_messages
        if not _is_system_message(msg) and _is_meaningful_message(msg)
    ]

    if passed_filter:
        console.print(
            f"[bold green]Sample of first messages that PASSED filters:[/bold green] ({len(passed_filter)} total)"
        )
        table = Table(show_header=True, header_style="bold green")
        table.add_column("Message", style="dim", no_wrap=False)
        table.add_column("Conv ID", style="cyan", width=10)
        table.add_column("Project", style="green", width=15)

        for msg, conv_id, project in passed_filter[:15]:
            table.add_row(msg[:150], conv_id, project)

        console.print(table)
        console.print()

    # Compare first vs last message usage
    console.print("[bold magenta]First vs Last Message Comparison:[/bold magenta]")
    console.print(
        f"Average first message length: {sum(len(m[0]) for m in first_messages) / len(first_messages):.0f} chars"
    )
    console.print(
        f"Average last message length: {sum(len(m[0]) for m in last_messages) / len(last_messages):.0f} chars"
    )


if __name__ == "__main__":
    analyze_conversation_patterns()
