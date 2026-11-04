"""Global test configuration."""

import pytest

# Patch time.sleep for slow tests
@pytest.fixture(autouse=True)
def patch_time_sleep(monkeypatch):
    """Auto-patch time.sleep to avoid real waits in tests."""
    monkeypatch.setattr('time.sleep', lambda *_: None)
    monkeypatch.setattr('backend.simulation.time.sleep', lambda *_: None)
    monkeypatch.setattr('backend.llm_guard.time.sleep', lambda *_: None)
