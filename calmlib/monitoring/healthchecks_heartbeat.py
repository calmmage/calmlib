#!/usr/bin/env python3
"""
Healthchecks Heartbeat Integration for Calmmage.

This module provides reusable functions for sending heartbeats to Healthchecks.io
monitoring service, replacing the existing Cronitor functionality with
feature parity using healthchecks.io's auto-provisioning capabilities.
"""

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from loguru import logger

from calmlib.utils.env_discovery import find_calmmage_env_key


def build_healthchecks_url(
    monitor_key: str, ping_key: str | None = None, base_url: str | None = None
) -> str:
    """
    Build Healthchecks.io ping URL using calmmage conventions.

    Args:
        monitor_key: Monitor identifier (job name, etc.)
        ping_key: Healthchecks ping key (defaults to CALMMAGE_HEALTHCHECKS_PING_KEY env var)
        base_url: Base URL for healthchecks instance

    Returns:
        str: Complete Healthchecks ping URL
    """
    if ping_key is None:
        ping_key = find_calmmage_env_key("CALMMAGE_HEALTHCHECKS_PING_KEY")

    if base_url is None:
        base_url = find_calmmage_env_key("CALMMAGE_HEALTHCHECKS_BASE_URL")

    return f"{base_url}/ping/{ping_key}/{monitor_key}"


def send_healthchecks_heartbeat(
    monitor_key: str,
    state: str | None = None,
    message: str | None = None,
    ping_key: str | None = None,
    base_url: str | None = None,
    auto_create: bool = True,
    timeout: int = 10,
    verbose: bool = False,
    expected_period: int | None = None,  # Expected period in seconds
    grace_period: int | None = None,  # Grace period in seconds
) -> dict[str, Any]:
    """
    Send heartbeat to Healthchecks.io, with auto-provisioning support.

    Args:
        monitor_key: Monitor identifier
        state: Healthchecks state ('start', 'fail', or None for success)
        message: Optional message to include
        ping_key: Healthchecks ping key (defaults to CALMMAGE_HEALTHCHECKS_PING_KEY env var)
        base_url: Base URL for healthchecks instance
        auto_create: Whether to auto-create checks that don't exist
        timeout: Request timeout in seconds
        verbose: Whether to print detailed debugging info
        expected_period: Expected period between pings in seconds (for auto-created checks)
        grace_period: Grace period after expected period in seconds (for auto-created checks)

    Returns:
        dict: Response information including success status and details
    """
    if base_url is None:
        base_url = find_calmmage_env_key("CALMMAGE_HEALTHCHECKS_BASE_URL")
    try:
        # Build URL using established calmmage conventions
        url = build_healthchecks_url(monitor_key, ping_key, base_url)

        # Add state suffix if specified
        if state:
            url += f"/{state}"

        # Add query parameters
        params = {}
        if auto_create:
            params["create"] = "1"
        # Note: timeout and grace parameters are NOT supported in ping URLs
        # They must be configured via the Management API when creating checks

        if params:
            url += "?" + urlencode(params)

        if verbose:
            logger.debug(f"📡 Pinging Healthchecks: {monitor_key}")
            if state:
                logger.debug(f"   State: {state}")
            if message:
                logger.debug(f"   Message: {message}")

        # Send POST with message body if provided
        data = None
        if message:
            data = message.encode("utf-8")

        with urlopen(url, data=data, timeout=timeout) as response:
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
        if verbose:
            logger.debug(f"   ❌ {error_msg}")
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
        if verbose:
            logger.debug(f"   ❌ {error_msg}")
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
        if verbose:
            logger.debug(f"   ❌ {error_msg}")
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
        if verbose:
            logger.debug(f"   ❌ {error_msg}")
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
    ping_key: str | None = None,
    base_url: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Send job status heartbeat mapped from calmmage job statuses.

    Args:
        job_name: Job identifier
        status: Calmmage job status (SUCCESS, FAIL, NO_CHANGE, etc.)
        notes: Optional notes/message
        ping_key: Healthchecks ping key (defaults to CALMMAGE_HEALTHCHECKS_PING_KEY env var)
        base_url: Base URL for healthchecks instance
        verbose: Whether to print detailed debugging info

    Returns:
        dict: Heartbeat response
    """
    # Map calmmage job statuses to Healthchecks states
    healthchecks_state = map_job_status_to_healthchecks_state(status)

    # Build message
    if notes:
        message = f"Job '{job_name}' {status.lower()}: {notes}"
    else:
        message = f"Job '{job_name}' {status.lower()}"

    return send_healthchecks_heartbeat(
        monitor_key=job_name,
        state=healthchecks_state,
        message=message,
        ping_key=ping_key,
        base_url=base_url,
        verbose=verbose,
    )


def map_job_status_to_healthchecks_state(status: str) -> str | None:
    """
    Map calmmage job status to Healthchecks state.

    Args:
        status: Calmmage job status (SUCCESS, FAIL, NO_CHANGE, etc.)

    Returns:
        Optional[str]: Healthchecks state ('start', 'fail', or None for success)
    """
    # Map based on JobStatus enum from job_runner.py
    # Healthchecks has 3 states: success (no suffix), start, fail
    status_upper = status.upper()

    if status_upper in {"SUCCESS", "success"}:
        return None  # Success ping (no suffix)
    elif status_upper in {"NO_CHANGE", "no_change"}:
        return None  # Success ping for no-change scenarios
    elif status_upper in {"REQUIRES_ATTENTION", "requires_attention"}:
        return "start"  # Use start to indicate attention needed
    elif status_upper in {"FAIL", "HANGING", "fail", "hanging"}:
        return "fail"
    else:
        # Default to failure for unknown states to err on the side of alerting
        logger.warning(f"Unknown job status '{status}', defaulting to 'fail' state")
        return "fail"


# Convenience functions for job lifecycle
def send_job_start(
    job_name: str,
    ping_key: str | None = None,
    base_url: str | None = None,
    verbose: bool = False,
    expected_period: int | None = None,
    grace_period: int | None = None,
) -> dict[str, Any]:
    """Send job start heartbeat."""
    return send_healthchecks_heartbeat(
        monitor_key=job_name,
        state="start",
        message=f"Job '{job_name}' started",
        ping_key=ping_key,
        base_url=base_url,
        verbose=verbose,
        expected_period=expected_period,
        grace_period=grace_period,
    )


def send_job_complete(
    job_name: str,
    message: str | None = None,
    ping_key: str | None = None,
    base_url: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Send job completion heartbeat."""
    final_message = message or f"Job '{job_name}' completed successfully"
    return send_healthchecks_heartbeat(
        monitor_key=job_name,
        state=None,  # Success ping
        message=final_message,
        ping_key=ping_key,
        base_url=base_url,
        verbose=verbose,
    )


def send_job_failure(
    job_name: str,
    error_message: str | None = None,
    ping_key: str | None = None,
    base_url: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Send job failure heartbeat."""
    final_message = error_message or f"Job '{job_name}' failed"
    return send_healthchecks_heartbeat(
        monitor_key=job_name,
        state="fail",
        message=final_message,
        ping_key=ping_key,
        base_url=base_url,
        verbose=verbose,
    )


# Convenience alias for simple heartbeat sending
def send_heartbeat(
    monitor_key: str,
    state: str | None = None,
    message: str | None = None,
    ping_key: str | None = None,
    base_url: str | None = None,
    verbose: bool = False,
) -> bool:
    """
    Simple heartbeat function with success/failure semantics.

    Args:
        monitor_key: Monitor identifier
        state: State to send ('start', 'fail', or None for success)
        message: Optional message to include
        ping_key: Healthchecks ping key (defaults to CALMMAGE_HEALTHCHECKS_PING_KEY env var)
        base_url: Base URL for healthchecks instance
        verbose: Whether to print detailed debugging info

    Returns:
        bool: True if heartbeat was sent successfully
    """
    try:
        result = send_healthchecks_heartbeat(
            monitor_key, state, message, ping_key, base_url, verbose=verbose
        )
        return result["success"]
    except Exception as e:
        if verbose:
            logger.debug(f"Healthchecks heartbeat failed (non-fatal): {e}")
        return False
