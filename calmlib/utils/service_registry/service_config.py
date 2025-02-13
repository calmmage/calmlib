"""Simple utilities for configuring services in the registry.

Example:
    ```python
    from api.utils.service_config import add_service

    # Configure a cloud service that should ping every 5 minutes
    add_service("my-api", expected_period=300)  # 5 minutes

    # Configure a daily job
    add_service(
        "daily-cleanup",
        service_type="local_job",
        expected_period=24*3600,  # 24 hours
        dead_after=2*24*3600  # Consider dead after 2 days
    )
    ```
"""

import httpx
from enum import Enum
from loguru import logger
from typing import Optional, Dict, Any


class ServiceType(str, Enum):
    """Type of service being monitored"""

    CLOUD_SERVICE = "cloud_service"  # Long-running cloud service
    LOCAL_JOB = "local_job"  # Periodic local job that can disappear sometimes


def setup_service(
    service_key: str,
    service_type: Optional[str] = None,
    expected_period: Optional[int] = None,
    dead_after: Optional[int] = None,
) -> Dict[str, Any]:
    """Configure a service in the registry.

    Args:
        service_key: Unique identifier for the service
        service_type: Type of service ("cloud_service" or "local_job")
        expected_period: Time in seconds between expected heartbeats
        dead_after: Time in seconds after which to consider service dead
        initial_status: Initial status to set. If None, status won't be changed

    Returns:
        Updated service configuration

    Raises:
        httpx.HTTPError: If request fails
        ValueError: If CALMMAGE_SERVICE_REGISTRY_URL is not set
    """

    from calmlib.utils.service_registry.heartbeat import get_api_url

    api_url = get_api_url()
    if not api_url:
        raise ValueError("CALMMAGE_SERVICE_REGISTRY_URL not set")

    try:
        # Build request body
        request_data = {
            "service_key": service_key,
            "service_type": service_type,
            "expected_period": expected_period,
            "dead_after": dead_after,
        }
        # Remove None values
        request_data = {k: v for k, v in request_data.items() if v is not None}

        response = httpx.post(f"{api_url}/configure-service", json=request_data)
        response.raise_for_status()
        service = response.json()

        logger.info(f"Service {service_key} configured successfully")
        logger.info(f"Type: {service.get('service_type', 'default')}")
        if service.get("expected_period"):
            logger.info(f"Expected period: {service['expected_period']} seconds")
        if service.get("dead_after"):
            logger.info(f"Dead after: {service['dead_after']} seconds")

        return service
    except Exception as e:
        logger.error(f"Failed to configure service {service_key}: {e}")
        raise
