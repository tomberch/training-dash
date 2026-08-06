"""Shared datetime serialisation utilities for API response serialisers.

All datetimes stored in the database are naive UTC
(TIMESTAMP WITHOUT TIME ZONE). Without an explicit offset suffix,
JavaScript's ``new Date()`` treats the string as *local* time rather than
UTC, causing displayed times to shift by the viewer's UTC offset.

``utc_str`` appends ``+00:00`` so browsers parse the value as UTC and
``toLocaleString()`` / ``toLocaleDateString()`` etc. convert it to the
viewer's local timezone correctly.

Date-only values (``datetime.date`` objects) should use ``.isoformat()``
directly — they have no timezone component.
"""

from datetime import datetime


def utc_str(dt: datetime) -> str:
    """Serialise a naive UTC datetime to ISO 8601 with explicit UTC offset."""
    return dt.isoformat() + "+00:00"
