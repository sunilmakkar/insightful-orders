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
    assert isinstance(get_config("development"), DevConfig)
    assert isinstance(get_config("testing"), TestConfig)
    assert isinstance(get_config("production"), ProdConfig)


def test_get_config_invalid_key():
    with pytest.raises(RuntimeError):
        get_config("invalid-env")