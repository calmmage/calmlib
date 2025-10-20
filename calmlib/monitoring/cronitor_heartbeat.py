#!/usr/bin/env python3
"""
Cronitor Heartbeat Integration for Calmmage.

This module provides reusable functions for sending heartbeats to Cronitor
monitoring service, building on the existing ping_cronitor functionality
and using established calmmage environment variable conventions.
"""

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from calmlib.utils.env_discovery import find_calmmage_env_key


def build_cronitor_url(monitor_key: str, cronitor_id: str | None = None) -> str:
    """
    Build Cronitor heartbeat URL using calmmage conventions.

    Args:
        monitor_key: Monitor identifier (job name, etc.)
        cronitor_id: Cronitor ID (defaults to CALMMAGE_CRONITOR_ID env var)

    Returns:
        str: Complete Cronitor heartbeat URL
    """
    if cronitor_id is None:
        cronitor_id = find_calmmage_env_key("CALMMAGE_CRONITOR_ID")

    return f"https://cronitor.link/p/{cronitor_id}/{monitor_key}"


def send_cronitor_heartbeat(
    monitor_key: str,
    state: str | None = None,
    message: str | None = None,
    cronitor_id: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """
    Send heartbeat to Cronitor, building on existing ping_cronitor functionality.

    Args:
        monitor_key: Monitor identifier
        state: Cronitor state ('run', 'complete', 'fail', or None for basic heartbeat)
        message: Optional message to include
        cronitor_id: Cronitor ID (defaults to CALMMAGE_CRONITOR_ID env var)
        timeout: Request timeout in seconds

    Returns:
        dict: Response information including success status and details
    """
    try:
        # Build URL using established calmmage conventions
        url = build_cronitor_url(monitor_key, cronitor_id)

        # Add query parameters
        params = {}
        if state:
            params["state"] = state
        if message:
            params["message"] = message

        if params:
            url += "?" + urlencode(params)

        print(f"📡 Pinging Cronitor: {monitor_key}")
        if state:
            print(f"   State: {state}")
        if message:
            print(f"   Message: {message}")

        # Use the same HTTP logic as the existing ping_cronitor
        with urlopen(url, timeout=timeout) as response:
            response_text = response.read().decode("utf-8")

            return {
                "success": True,
                "status_code": response.status,
                "response_text": response_text.strip(),
                "url": url,
                "monitor_key": monitor_key,
                "state": state,
                "error": None,
            }

    except HTTPError as e:
        error_msg = f"HTTP error {e.code}: {e.reason}"
        print(f"   ❌ {error_msg}")
        return {
            "success": False,
            "status_code": e.code,
            "response_text": None,
            "url": url if "url" in locals() else None,
            "monitor_key": monitor_key,
            "state": state,
            "error": error_msg,
        }

    except URLError as e:
        error_msg = f"URL error: {e.reason}"
        print(f"   ❌ {error_msg}")
        return {
            "success": False,
            "status_code": None,
            "response_text": None,
            "url": url if "url" in locals() else None,
            "monitor_key": monitor_key,
            "state": state,
            "error": error_msg,
        }

    except TimeoutError:
        error_msg = f"Request timed out after {timeout} seconds"
        print(f"   ❌ {error_msg}")
        return {
            "success": False,
            "status_code": None,
            "response_text": None,
            "url": url if "url" in locals() else None,
            "monitor_key": monitor_key,
            "state": state,
            "error": error_msg,
        }

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"   ❌ {error_msg}")
        return {
            "success": False,
            "status_code": None,
            "response_text": None,
            "url": url if "url" in locals() else None,
            "monitor_key": monitor_key,
            "state": state,
            "error": error_msg,
        }


def send_job_heartbeat(
    job_name: str,
    status: str,
    notes: str | None = None,
    cronitor_id: str | None = None,
) -> dict[str, Any]:
    """
    Send job status heartbeat mapped from calmmage job statuses.

    Args:
        job_name: Job identifier
        status: Calmmage job status (SUCCESS, FAIL, NO_CHANGE, etc.)
        notes: Optional notes/message
        cronitor_id: Cronitor ID (defaults to CALMMAGE_CRONITOR_ID env var)

    Returns:
        dict: Heartbeat response
    """
    # Map calmmage job statuses to Cronitor states
    cronitor_state = map_job_status_to_cronitor_state(status)

    # Build message
    if notes:
        message = f"Job '{job_name}' {status.lower()}: {notes}"
    else:
        message = f"Job '{job_name}' {status.lower()}"

    return send_cronitor_heartbeat(
        monitor_key=job_name,
        state=cronitor_state,
        message=message,
        cronitor_id=cronitor_id,
    )


def map_job_status_to_cronitor_state(status: str) -> str:
    """
    Map calmmage job status to Cronitor state.

    Args:
        status: Calmmage job status (SUCCESS, FAIL, NO_CHANGE, etc.)

    Returns:
        str: Cronitor state ('tick', 'run', 'complete', or 'fail')
    """
    # Map based on JobStatus enum from job_runner.py
    # Cronitor has 4 statuses: fail, complete, run, tick
    status_upper = status.upper()

    if status_upper in {"SUCCESS", "success"}:
        return "complete"
    elif status_upper in {"NO_CHANGE", "no_change"}:
        return "tick"
    elif status_upper in {"REQUIRES_ATTENTION", "requires_attention"}:
        return "run"
    elif status_upper in {"FAIL", "HANGING", "fail", "hanging"}:
        return "fail"
    else:
        # Default to failure for unknown states to err on the side of alerting
        print(f"⚠️  Unknown job status '{status}', defaulting to 'fail' state")
        return "fail"


# Convenience functions for job lifecycle
def send_job_start(job_name: str, cronitor_id: str | None = None) -> dict[str, Any]:
    """Send job start heartbeat."""
    return send_cronitor_heartbeat(
        monitor_key=job_name,
        state="run",
        message=f"Job '{job_name}' started",
        cronitor_id=cronitor_id,
    )


def send_job_complete(
    job_name: str, message: str | None = None, cronitor_id: str | None = None
) -> dict[str, Any]:
    """Send job completion heartbeat."""
    final_message = message or f"Job '{job_name}' completed successfully"
    return send_cronitor_heartbeat(
        monitor_key=job_name,
        state="complete",
        message=final_message,
        cronitor_id=cronitor_id,
    )


def send_job_failure(
    job_name: str,
    error_message: str | None = None,
    cronitor_id: str | None = None,
) -> dict[str, Any]:
    """Send job failure heartbeat."""
    final_message = error_message or f"Job '{job_name}' failed"
    return send_cronitor_heartbeat(
        monitor_key=job_name,
        state="fail",
        message=final_message,
        cronitor_id=cronitor_id,
    )


def safe_send_heartbeat(
    monitor_key: str,
    state: str | None = None,
    message: str | None = None,
    cronitor_id: str | None = None,
) -> bool:
    """
    Safely send heartbeat, returning success status without raising exceptions.

    This function is designed to be called from job execution contexts where
    heartbeat failures should not interrupt the main job logic.

    Returns:
        bool: True if heartbeat was sent successfully, False otherwise
    """
    try:
        result = send_cronitor_heartbeat(monitor_key, state, message, cronitor_id)
        return result["success"]
    except Exception as e:
        print(f"⚠️  Cronitor heartbeat failed (non-fatal): {e}")
        return False
