"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """Fixture providing path to test data directory."""
    return Path(__file__).parent.parent / "test"


@pytest.fixture
def gex_fixture(test_data_dir):
    """Fixture providing live GEX data from OptionAlpha API."""
    import json
    with open(test_data_dir / "gex.json") as f:
        return json.load(f)[0]


@pytest.fixture
def histgex_fixture(test_data_dir):
    """Fixture providing historical GEX data from OptionAlpha API."""
    import json
    with open(test_data_dir / "histgex.json") as f:
        return json.load(f)[0]
