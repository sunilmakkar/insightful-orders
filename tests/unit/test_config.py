"""
Unit tests for config module.

Covers:
    - Ensures `get_config` returns the correct configuration class
      for each valid environment key ("development", "testing", "production").
    - Provides coverage for the happy-path branches in config.py.

Notes:
    - The invalid key branch is already tested elsewhere.
    - This test focuses only on verifying correct mappings.
"""

import pytest
from app.config import get_config, DevConfig, TestConfig, ProdConfig

def test_get_config_valid_keys():
    assert get_config("development") is DevConfig
    assert get_config("testing") is TestConfig
    assert get_config("production") is ProdConfig
