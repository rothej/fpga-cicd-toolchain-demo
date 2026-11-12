# verif/common/tests/conftest.py
import os
import random
import zlib

import pytest

BASE_SEED = int(os.environ.get("TEST_SEED", "0"))


def pytest_report_header(config):
    return f"random base seed: {BASE_SEED} (override with TEST_SEED=<int>)"


@pytest.fixture(autouse=True)
def _seed_random(request):
    # Derive a per-test seed from the test's node ID.
    seed = BASE_SEED ^ zlib.crc32(request.node.nodeid.encode())
    random.seed(seed)
    yield
