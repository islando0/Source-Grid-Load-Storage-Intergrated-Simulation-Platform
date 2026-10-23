import numpy as np
import pytest

from src.loader import load_scenario_a, load_scenario_b, tariff_for_index
from src.simulate import SimulationParams, simulate


def test_scenario_a_shape():
    s = load_scenario_a()
    assert s.hours == 5832
    assert 0.0 <= s.wind_cf.min() and s.wind_cf.max() <= 1.0
    assert 0.0 <= s.pv_cf.min() and s.pv_cf.max() <= 1.0
    assert s.load_mw.min() > 0
    assert s.price_buy.min() >= 0.3


def test_tariff_hours():
    import pandas as pd

    idx = pd.date_range("2026-01-01", periods=24, freq="h")
    price = tariff_for_index(idx)
    assert price[0] == 0.35
    assert price[8] == 0.75
    assert price[17] == 1.15
    assert price[21] == 0.75


@pytest.mark.parametrize("loader", [load_scenario_a, load_scenario_b])
def test_simulation_balance_and_bounds(loader):
    s = loader()
    params = SimulationParams(C_w=50, C_pv=80, C_b=20, E_b=80)
    result = simulate(s, params, keep_series=True)
    ser = result.series
    assert ser is not None

    avail = 50 * s.wind_cf + 80 * s.pv_cf
    supply = (
        avail
        + np.array(ser["battery_discharge"])
        + np.array(ser["grid_buy"])
        + np.array(ser["ens"])
    )
    demand = (
        s.load_mw
        + np.array(ser["battery_charge"])
        + np.array(ser["grid_sell"])
        + np.array(ser["curtail"])
    )
    assert np.abs(supply - demand).max() < 1e-6

    soc = np.array(ser["soc"])
    assert soc.min() >= params.soc_min - 1e-9
    assert soc.max() <= params.soc_max + 1e-9

    assert result.annual_cost > 0
    assert 0.0 <= result.reliability <= 1.0
    assert 0.0 <= result.soc_in_band_ratio <= 1.0
    assert 0.1 < result.lcoe < 2.0


def test_invalid_bounds():
    with pytest.raises(ValueError):
        SimulationParams(C_w=1, C_pv=1, C_b=1, E_b=1, soc_min=0.5, soc_soft_min=0.3).validate()
