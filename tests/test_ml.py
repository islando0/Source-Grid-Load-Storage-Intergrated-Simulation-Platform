import numpy as np

from src.loader import load_scenario_a
from src.ml.pv import (
    apply_to_scenario,
    compare_on_scenario,
    model_info,
    predict_cf,
    training_frame,
)


def test_external_training_frame():
    frame = training_frame()
    assert len(frame) > 2000
    assert {"irradiance_kw_m2", "ambient_temp_c", "cf"}.issubset(frame.columns)
    assert frame["cf"].between(0.0, 1.0).all()
    assert frame["timestamp"].is_monotonic_increasing


def test_model_info_available():
    info = model_info()
    assert info["available"] is True
    assert info["metrics"]["r2"] > 0.9
    assert info["metrics"]["mae"] < 0.03


def test_predict_and_apply():
    scenario = load_scenario_a()
    cf = predict_cf(scenario.ghi_wm2[:48], scenario.temp_c[:48], scenario.timestamps[:48])
    assert len(cf) == 48
    assert cf.min() >= 0.0 and cf.max() <= 1.0

    ml = apply_to_scenario(scenario)
    assert ml.meta["pv_model"] == "ml_external_solar"
    assert len(ml.pv_cf) == scenario.hours
    assert ml.ghi_wm2 is not None


def test_compare_on_scenario():
    comparison = compare_on_scenario(load_scenario_a())
    assert comparison["rows"] == 5832
    assert comparison["corr"] > 0.95
    assert len(comparison["ml_cf"]) == len(comparison["physical_cf"])
    assert np.isfinite(comparison["mae"])
