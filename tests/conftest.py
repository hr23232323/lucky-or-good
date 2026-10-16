import json

import pytest

from lucky.synthetic import SyntheticConfig, generate

# Small markets keep the suite fast. Both span the 2026-03-27 schema switch.
NOISE = SyntheticConfig(start="2021-01-04", end="2026-06-30", n_stocks=40, edge=0.0, seed=1)
EDGE = SyntheticConfig(start="2021-01-04", end="2026-06-30", n_stocks=40, edge=0.004, seed=2)


@pytest.fixture(scope="session")
def noise_market(tmp_path_factory):
    root = tmp_path_factory.mktemp("noise_market")
    generate(root, NOISE)
    return root


@pytest.fixture(scope="session")
def edge_market(tmp_path_factory):
    root = tmp_path_factory.mktemp("edge_market")
    generate(root, EDGE)
    return root


@pytest.fixture(scope="session")
def noise_truth(noise_market):
    return json.loads((noise_market / "truth.json").read_text())
