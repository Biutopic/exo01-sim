import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exo01.config import load_config, resolve  # noqa: E402
from exo01.analysis import evaluate  # noqa: E402
from exo01.reference import Reference  # noqa: E402


@pytest.fixture(scope="session")
def ref():
    return Reference(ROOT / "data" / "reference_v3")


@pytest.fixture(scope="session")
def baseline():
    return load_config("baseline")


@pytest.fixture(scope="session")
def illustrative():
    return load_config("illustrative")


@pytest.fixture(scope="session")
def ill_result(illustrative):
    """EXO-only illustrative result (pure hydrostatic balance)."""
    return evaluate(resolve(illustrative, {"host_boat": {"included": False}}))


@pytest.fixture(scope="session")
def ill_boat_result(illustrative):
    """EXO + moored boat (coupled static equilibrium with tension-only lines)."""
    return evaluate(illustrative)


@pytest.fixture(scope="session")
def symmetric_cfg(illustrative):
    """Deliberately symmetric loading: the single electronics box is moved onto the centreline."""
    return resolve(illustrative, {"components": {"ELECTRONICS_50": {"com_m": [1.6, 0.0, 0.95]}}, "host_boat": {"included": False}})


@pytest.fixture(scope="session")
def sym_result(symmetric_cfg):
    return evaluate(symmetric_cfg)
