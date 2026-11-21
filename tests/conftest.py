"""Shared fixtures. Tests run on the organizer's synthetic dataset in data/raw/data (read-only)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.audit import run_audit  # noqa: E402
from src.data import load_all  # noqa: E402


@pytest.fixture(scope="session")
def t():
    return load_all()


@pytest.fixture(scope="session")
def findings(t):
    return run_audit(t)


@pytest.fixture(scope="session")
def findings_all(t):
    return run_audit(t, include_informational=True)
