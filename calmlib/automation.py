"""
Automation utilities for local job runner.

Provides shared data models and utilities for automated job execution.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from calmlib.monitoring import send_job_heartbeat


class JobStatus(Enum):
    """Job execution status for monitoring and reporting."""

    SUCCESS = "success"
    FAIL = "fail"
    NO_CHANGE = "no_change"
    HANGING = "hanging"
    REQUIRES_ATTENTION = "requires_attention"


class JobResult(BaseModel):
    """Result of a job execution."""

    status: JobStatus
    notes: Optional[str] = None
    changes: list[str] = []


# Emoji mappings for display
STATUS_EMOJIS = {
    JobStatus.SUCCESS: "✅",
    JobStatus.FAIL: "❌",
    JobStatus.NO_CHANGE: "⚪",
    JobStatus.REQUIRES_ATTENTION: "⚠️",
    JobStatus.HANGING: "❌",
}


def send_heartbeat(job_name: str, result: JobResult, verbose: bool = False) -> None:
    """Send monitoring heartbeat for job result."""
    try:
        status = result.status.value.upper()
        notes = result.notes or f"Job completed with status: {status}"
        send_job_heartbeat(job_name, status, notes, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"⚠️  Failed to send heartbeat for {job_name}: {e}")


def print_result_table(results: list[tuple[str, JobResult]]) -> None:
    """Print results table with Rich formatting.

    Args:
        results: List of (job_name, JobResult) tuples
    """
    console = Console()

    table = Table(title="Job Results")
    table.add_column("Job", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Notes", style="white")
    table.add_column("Changes", justify="right", style="green")

    for job_name, result in results:
        emoji = STATUS_EMOJIS.get(result.status, "❓")
        status_display = f"{emoji} {result.status.value.upper()}"
        notes = result.notes or "No notes"
        changes_count = str(len(result.changes)) if result.changes else "0"

        table.add_row(job_name, status_display, notes, changes_count)

    console.print(table)
