"""Garmin Connect integration."""

from trainingdash.integrations.garmin.client import (
    GarminActivity,
    GarminAPIError,
    GarminClient,
    GarminClientProtocol,
    GarminMFARequired,
    get_garmin_client,
    set_garmin_client_factory,
)

__all__ = [
    "GarminAPIError",
    "GarminActivity",
    "GarminClient",
    "GarminClientProtocol",
    "GarminMFARequired",
    "get_garmin_client",
    "set_garmin_client_factory",
]
