import numpy as np
import pytest

from src.loader import load_scenario_a
from src.optimize import BOUNDS, duration_violation, evaluate, gwo, make_params, pso


@pytest.fixture(scope="module")
def scenario():
    return load_scenario_a()


def test_duration_violation():
    assert duration_violation(make_params(np.array([0, 0, 0, 0]))) == 0.0
    assert duration_violation(make_params(np.array([0, 0, 50, 0]))) == 2.0
    assert duration_violation(make_params(np.array([0, 0, 50, 100]))) == 0.0
    assert duration_violation(make_params(np.array([0, 0, 50, 400]))) == 2.0


def test_evaluate_no_storage(scenario):
    ev = evaluate(np.array([80.0, 120.0, 0.0, 0.0]), scenario)
    assert ev.fitness > 0
    assert ev.duration_violation == 0.0
    assert ev.metrics["soc_in_band_ratio"] == 0.0


def test_pso_small(scenario):
    result = pso(scenario, n_particles=4, n_iters=2, seed=7, verbose=False)
    assert len(result.best_x) == 4
    assert np.isfinite(result.best_fitness)
    assert len(result.history) == 2
    assert result.n_evals == 8
    assert result.runtime_s > 0
    x = np.array(result.best_x)
    assert np.all(x >= BOUNDS[:, 0] - 1e-9)
    assert np.all(x <= BOUNDS[:, 1] + 1e-9)
    assert result.best_metrics["annual_cost"] > 0


def test_gwo_small(scenario):
    result = gwo(scenario, n_wolves=4, n_iters=2, seed=7, verbose=False)
    assert len(result.best_x) == 4
    assert np.isfinite(result.best_fitness)
    assert len(result.history) == 2
    assert result.n_evals == 8
    assert result.runtime_s > 0
