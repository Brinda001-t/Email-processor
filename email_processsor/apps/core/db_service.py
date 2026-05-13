"""
DB query service for order tracking.
Replace the stub implementations below with real DB queries
once the order management DB connection is configured.
"""

import logging

logger = logging.getLogger(__name__)


def get_order_status(order_number: str) -> dict:
    """
    Query the order management DB for the status of a given order number.

    Returns a dict with keys:
        order_number   : str
        status         : str  (e.g. "Processing", "Shipped", "Delivered")
        expected_date  : str  (e.g. "2026-05-15")
        notes          : str  (any additional info)
        found          : bool (False if order number not found in DB)

    TODO: Replace stub with real DB query.
    Example (SQLAlchemy / psycopg2 / Django ORM — whichever applies):
        row = OrderTable.objects.get(order_number=order_number)
        return {"order_number": ..., "status": row.status, ...}
    """
    logger.warning("get_order_status called with stub implementation for order %s", order_number)
    return {
        "order_number": order_number,
        "status": "Unknown",
        "expected_date": "N/A",
        "notes": "Order lookup not yet connected to database.",
        "found": False,
    }


def get_driver_status(order_number: str) -> dict:
    """
    Query the delivery/driver tables for the driver location and ETA
    for a given order number.

    Returns a dict with keys:
        order_number   : str
        driver_name    : str
        current_location: str
        eta            : str  (e.g. "2026-05-12 14:30 UTC")
        notes          : str
        found          : bool (False if order number not found in DB)

    TODO: Replace stub with real DB query.
    Example:
        row = DeliveryTable.objects.get(order_number=order_number)
        return {"driver_name": row.driver.name, "eta": row.eta, ...}
    """
    logger.warning("get_driver_status called with stub implementation for order %s", order_number)
    return {
        "order_number": order_number,
        "driver_name": "N/A",
        "current_location": "N/A",
        "eta": "N/A",
        "notes": "Driver lookup not yet connected to database.",
        "found": False,
    }
