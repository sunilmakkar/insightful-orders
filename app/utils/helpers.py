"""
Utility helpers for Insightful-Orders.

Responsibilities:
    - Pagination: Apply limit/offset to a SQLAlchemy query and serialize results.
    - Time parsing: Convert compact window strings (e.g., '30d', '6m') to timedeltas.
    - Date parsing: Parse 'YYYY-MM' or 'YYYY-MM-DD' strings into datetime objects.
    - Alerts: Produce a canonical Redis/WebSocket channel name for a merchant.

All helpers are framework-light and safe to reuse across blueprints/services.
"""

from flask import request
from datetime import timedelta, datetime
from typing import Optional 


# ----------------------------------------------------------------------
# Pagination Helper
# ----------------------------------------------------------------------
def paginate(query, serializer, default_page_size=20, max_page_size=100):
    """
    Paginate a SQLAlchemy query and serialize the results.

    Args:
        query (BaseQuery): The SQLAlchemy query to paginate.
        serializer (Schema): A Marshmallow schema instance for serializing items.
        default_page_size (int, optional): Default number of items per page. Defaults to 20.
        max_page_size (int, optional): Maximum allowed items per page. Defaults to 100.

    Returns:
        dict: A dictionary containing pagination metadata and serialized items:
              {
                  "page": current page number,
                  "page_size": number of items per page,
                  "items": serialized list of results,
                  "count": total number of items (ignoring pagination)
              }
    """
    try:
        # Read `page` and `page_size` from query params (defaulting if not provided)
        page = int(request.args.get("page", 1))
        page_size = min(
            int(request.args.get("page_size", default_page_size)),
            max_page_size
        )
    except ValueError:
        # Fallback to defaults if non-integer values are passed
        page, page_size = 1, default_page_size

    # Apply limit/offset to the query for pagination
    items = query.limit(page_size).offset((page - 1) * page_size).all()

    # Return pagination metadata + serialized data
    return {
        "page": page,
        "page_size": page_size,
        "items": serializer.dump(items, many=True),  # serialize the query results
        "count": query.order_by(None).count()  # total count without pagination
    }

# ----------------------------------------------------------------------
# Window String Parser
# ----------------------------------------------------------------------
def parse_window_str(window: str) -> timedelta:
    """
    Parse a compact window string like '30d', '12w', '6m', '1y' into a timedelta.
    Supports:
    - d = days
    - w = weeks
    - m = months (approx as 30 days)
    - y = year (approx as 365 days)
    """
    if not window or len(window) < 2:
        raise ValueError("Invalid window string")
    num, unit = int(window[:-1]), window[-1].lower()
    if unit == 'd':
        return timedelta(days=num)
    if unit == 'w':
        return timedelta(weeks=num)
    if unit == 'm':
        return timedelta(days=30 * num)
    if unit == 'y':
        return timedelta(days=365 * num)
    raise ValueError(f"Unsupported window unit: {unit}")

# ----------------------------------------------------------------------
# 'Monthish' Date Parser
# ----------------------------------------------------------------------
def parse_monthish(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a string in 'YYYY-MM' or 'YYYY-MM-DD' format into a datetime object.

    Args:
        date_str (str | None): Input string to parse. Can be:
            - 'YYYY-MM'      (interpreted as first day of that month)
            - 'YYYY-MM-DD'   (exact date)
            - None or ''     (returns None)

    Returns:
        datetime | None: A datetime object (00:00:00 time) if parsing succeeds,
                         otherwise None for invalid/empty input.
    """
    if not date_str:
        return None

    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None

# ----------------------------------------------------------------------
# Alerts Channel Helper
# ----------------------------------------------------------------------
def alerts_channel_for_merchant(merchant_id: int) -> str:
    """
    Return a standardized channel name for alerts for a given merchant.

    Example:
        merchant_id = 42 -> "alerts:merchant:42"
    """
    return f"alerts:merchant:{merchant_id}"