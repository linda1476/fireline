"""Shared pytest fixtures. Mock mode is forced BEFORE any fireline import so no test
touches the network. Live-API tests must be marked ``@pytest.mark.live`` and are skipped
unless FIRELINE_LIVE_TESTS=1 and MODEL_API_KEY are set.
"""

import os

os.environ["FIRELINE_MOCK"] = "1"

import pytest  # noqa: E402

from fireline.config import get_settings  # noqa: E402
from fireline.scenario import load_scenario  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real Meta Model API (needs key + FIRELINE_LIVE_TESTS=1)")


def pytest_collection_modifyitems(config, items):
    live_ok = os.environ.get("FIRELINE_LIVE_TESTS") == "1" and os.environ.get("MODEL_API_KEY")
    skip = pytest.mark.skip(reason="live API tests disabled (set FIRELINE_LIVE_TESTS=1 and MODEL_API_KEY)")
    for item in items:
        if "live" in item.keywords and not live_ok:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def scenario():
    return load_scenario()


@pytest.fixture
def state(scenario):
    return scenario.initial_state()


@pytest.fixture(scope="session")
def settings():
    s = get_settings(refresh=True)
    assert s.mock, "tests must run in mock mode"
    return s
