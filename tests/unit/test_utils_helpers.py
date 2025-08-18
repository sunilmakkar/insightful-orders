"""
Utility helper tests for Insightful-Orders.

Covers:
    - Window string parsing (e.g., "30d", "2w", "1m", "1y")
    - 'Monthish' date parsing ("YYYY-MM", "YYYY-MM-DD")
    - Alerts channel name generation

Functions under test:
    parse_window_str(window)
    parse_monthish(date_str)
    alerts_channel_for_merchant(merchant_id)

Notes:
    - Focuses on edge cases (invalid strings, None input).
    - Complements higher-level service logic.
"""

import pytest
from app.utils import helpers


# ----------------------------------------------------------------------
# Window String Parser
# ----------------------------------------------------------------------
def test_parse_window_str_valid():
    """parse_window_str should return correct timedelta for valid inputs."""
    assert helpers.parse_window_str("30d").days == 30
    assert helpers.parse_window_str("2w").days == 14
    assert helpers.parse_window_str("1m").days == 30
    assert helpers.parse_window_str("1y").days == 365


def test_parse_window_str_invalid():
    """parse_window_str should raise ValueError for invalid inputs."""
    with pytest.raises(ValueError):
        helpers.parse_window_str("")
    with pytest.raises(ValueError):
        helpers.parse_window_str("5z")


# ----------------------------------------------------------------------
# Monthish Date Parser
# ----------------------------------------------------------------------
def test_parse_monthish_valid_and_invalid():
    """parse_monthish should handle YYYY-MM, YYYY-MM-DD, invalid, and None inputs."""
    assert helpers.parse_monthish("2023-01").month == 1
    assert helpers.parse_monthish("2023-01-15").day == 15
    assert helpers.parse_monthish("not-a-date") is None
    assert helpers.parse_monthish(None) is None


# ----------------------------------------------------------------------
# Alerts Channel Helper
# ----------------------------------------------------------------------
def test_alerts_channel_for_merchant():
    """alerts_channel_for_merchant should return standardized channel names."""
    assert helpers.alerts_channel_for_merchant(42) == "alerts:merchant:42"
