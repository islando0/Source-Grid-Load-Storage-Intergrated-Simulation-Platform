"""外部公开光伏数据训练的容量因子模型。

训练集：Kaggle Solar Power Generation Data（Ani Kannal）的 Plant 1。
本项目只使用其 15 分钟级发电与气象观测，训练“辐照度/气温 → 光伏容量因子”
的回归模型，再把模型迁移到教师 03 数据的 GHI/温度上，作为物理折算模型的对照。

注意：
- 这是课程实验用的迁移分析，不代表目标电站的真实功率曲线；
- 训练数据不随项目再分发，运行 `scripts/prepare_external_solar.py` 可重新下载。
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.loader import ScenarioData

BASE_DIR = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = BASE_DIR / "data" / "external" / "solar_power_generation"
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "pv_cf_model.joblib"
META_PATH = MODEL_DIR / "pv_cf_metadata.json"

GEN_FILE = EXTERNAL_DIR / "Plant_1_Generation_Data.csv"
WEATHER_FILE = EXTERNAL_DIR / "Plant_1_Weather_Sensor_Data.csv"

# Plant 1 有 22 台约 1.4 MW 逆变器，聚合峰值约 29.15 MW，按 30 MW 装机归一化。
PLANT_CAPACITY_MW = 30.0
FEATURES = ["irradiance_kw_m2", "ambient_temp_c", "hour_sin", "hour_cos"]
DATASET_NAME = "Kaggle Solar Power Generation Data (Plant 1)"
DATASET_URL = "https://www.kaggle.com/datasets/anikannal/solar-power-generation-data"


def _read_external() -> pd.DataFrame:
    if not GEN_FILE.exists() or not WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"缺少外部训练数据：请先运行 python scripts/prepare_external_solar.py\n"
            f"期望文件：{GEN_FILE} 与 {WEATHER_FILE}"
        )

    gen = pd.read_csv(GEN_FILE)
    gen["timestamp"] = pd.to_datetime(gen["DATE_TIME"], dayfirst=True, errors="coerce")
    gen = gen.dropna(subset=["timestamp"])
    # 同一时刻有多台逆变器，先按时刻加总为电站级 AC/DC。
    gen = (
        gen.groupby("timestamp", as_index=False)[["AC_POWER", "DC_POWER"]]
        .sum()
        .sort_values("timestamp")
    )

    weather = pd.read_csv(WEATHER_FILE)
    weather["timestamp"] = pd.to_datetime(weather["DATE_TIME"], errors="coerce")
    weather = weather.dropna(subset=["timestamp"])
    weather = weather.sort_values("timestamp")

    merged = gen.merge(
        weather[
            ["timestamp", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE", "IRRADIATION"]
        ],
        on="timestamp",
        how="inner",
    )
    merged = merged.dropna(
        subset=["AC_POWER", "AMBIENT_TEMPERATURE", "IRRADIATION"]
    )
    merged["irradiance_kw_m2"] = merged["IRRADIATION"].clip(lower=0.0)
    merged["ambient_temp_c"] = merged["AMBIENT_TEMPERATURE"]
    merged["module_temp_c"] = merged["MODULE_TEMPERATURE"]
    merged["cf"] = (merged["AC_POWER"] / 1000.0 / PLANT_CAPACITY_MW).clip(0.0, 1.0)

    hour = merged["timestamp"].dt.hour + merged["timestamp"].dt.minute / 60.0
    merged["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    merged["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    return merged.sort_values("timestamp").reset_index(drop=True)


def training_frame() -> pd.DataFrame:
    """返回清洗后的外部训练表，便于 Notebook/测试复用。"""
    return _read_external()


def _chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.sort(frame["timestamp"].dt.normalize().unique())
    if len(dates) < 5:
        raise ValueError("训练数据日期不足，至少需要 5 天")
    split_at = dates[int(len(dates) * 0.8)]
    train = frame[frame["timestamp"] < split_at].copy()
    test = frame[frame["timestamp"] >= split_at].copy()
    if train.empty or test.empty:
        raise ValueError("按日期切分后训练集或测试集为空")
    return train, test


def _fit_model(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[RandomForestRegressor, dict]:
    # 沙箱环境禁止 Windows 命名管道，n_jobs=1 避免 joblib 进程池。
    model = RandomForestRegressor(
        n_estimators=240,
        max_depth=12,
        min_samples_leaf=8,
        max_features=0.9,
        n_jobs=1,
        random_state=42,
    )
    model.fit(train[FEATURES], train["cf"])
    pred = np.clip(model.predict(test[FEATURES]), 0.0, 1.0)

    # 物理基线：外部电站辐照度×0.82，按 1 kW/m² 近似 STC。
    baseline = np.clip(test["irradiance_kw_m2"].to_numpy() * 0.82, 0.0, 1.0)
    metrics = {
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_start": str(train["timestamp"].min()),
        "train_end": str(train["timestamp"].max()),
        "test_start": str(test["timestamp"].min()),
        "test_end": str(test["timestamp"].max()),
        "mae": float(mean_absolute_error(test["cf"], pred)),
        "rmse": float(mean_squared_error(test["cf"], pred) ** 0.5),
        "r2": float(r2_score(test["cf"], pred)),
        "baseline_mae": float(mean_absolute_error(test["cf"], baseline)),
        "baseline_rmse": float(mean_squared_error(test["cf"], baseline) ** 0.5),
        "physical_mae_note": "物理基线为 irradiance*0.82，仅作同测试集对照",
    }
    return model, metrics


def train_and_save() -> dict:
    """训练并保存模型与元数据，返回元数据。"""
    frame = _read_external()
    train, test = _chronological_split(frame)
    model, metrics = _fit_model(train, test)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "capacity_mw": PLANT_CAPACITY_MW,
        },
        MODEL_PATH,
    )
    meta = {
        "dataset": DATASET_NAME,
        "dataset_url": DATASET_URL,
        "license_note": "课程实验迁移分析；原始数据版权归数据集作者，不随项目再分发。",
        "plant_capacity_mw": PLANT_CAPACITY_MW,
        "features": FEATURES,
        "rows": int(len(frame)),
        "target": "AC_POWER 聚合 / 30 MW 装机，裁剪到 [0,1]",
        "model": "RandomForestRegressor(n_estimators=240, max_depth=12)",
        "split": "按日期前 80%/后 20% 时序切分",
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


@lru_cache(maxsize=1)
def load_artifact() -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"模型文件不存在：{MODEL_PATH}\n"
            f"请先训练：python -m src.ml.pv --train"
        )
    return joblib.load(MODEL_PATH)


def model_info() -> dict:
    """返回模型元数据；模型未训练时 available=False。"""
    if not META_PATH.exists():
        return {
            "available": False,
            "dataset": DATASET_NAME,
            "dataset_url": DATASET_URL,
            "message": "模型尚未训练，请运行 python -m src.ml.pv --train",
        }
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    meta["available"] = MODEL_PATH.exists()
    return meta


def predict_cf(
    irradiance_wm2: np.ndarray | list[float],
    ambient_temp_c: np.ndarray | list[float],
    timestamps: pd.DatetimeIndex | pd.Series,
) -> np.ndarray:
    """用外部电站模型预测容量因子，输入为 W/m² 与 ℃。"""
    artifact = load_artifact()
    irr = np.asarray(irradiance_wm2, dtype=float).reshape(-1)
    temp = np.asarray(ambient_temp_c, dtype=float).reshape(-1)
    index = pd.DatetimeIndex(timestamps)
    if len(irr) != len(temp) or len(irr) != len(index):
        raise ValueError("辐照度、温度、时间戳长度必须一致")

    hour = index.hour + index.minute / 60.0
    features = pd.DataFrame(
        {
            "irradiance_kw_m2": np.clip(irr / 1000.0, 0.0, None),
            "ambient_temp_c": temp,
            "hour_sin": np.sin(2 * np.pi * hour / 24.0),
            "hour_cos": np.cos(2 * np.pi * hour / 24.0),
        }
    )
    pred = artifact["model"].predict(features[artifact["features"]])
    return np.clip(pred, 0.0, 1.0)


def apply_to_scenario(scenario: ScenarioData) -> ScenarioData:
    """把外部模型迁移到 03 场景，返回替换了 pv_cf 的副本。"""
    if scenario.ghi_wm2 is None or scenario.temp_c is None:
        raise ValueError("该场景没有 GHI/温度字段，无法使用外部光伏模型")
    cf = predict_cf(scenario.ghi_wm2, scenario.temp_c, scenario.timestamps)
    meta = dict(scenario.meta)
    meta.update(
        {
            "pv_model": "ml_external_solar",
            "pv_model_dataset": DATASET_NAME,
            "pv_cf_mean_physical": float(np.mean(scenario.pv_cf)),
            "pv_cf_mean_ml": float(np.mean(cf)),
        }
    )
    return replace(scenario, pv_cf=cf, meta=meta)


def compare_on_scenario(scenario: ScenarioData) -> dict:
    """在同一 03 时间轴上比较物理折算与外部 ML 预测。"""
    if scenario.ghi_wm2 is None or scenario.temp_c is None:
        raise ValueError("该场景没有 GHI/温度字段，无法比较")
    ml = predict_cf(scenario.ghi_wm2, scenario.temp_c, scenario.timestamps)
    physical = np.asarray(scenario.pv_cf, dtype=float)
    diff = ml - physical
    return {
        "scenario": scenario.name,
        "rows": int(len(ml)),
        "ml_cf_mean": float(ml.mean()),
        "physical_cf_mean": float(physical.mean()),
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "max_abs_diff": float(np.max(np.abs(diff))),
        "corr": float(np.corrcoef(ml, physical)[0, 1]),
        "ml_cf_max": float(ml.max()),
        "physical_cf_max": float(physical.max()),
        "timestamps": [str(t) for t in scenario.timestamps],
        "ml_cf": [float(v) for v in ml],
        "physical_cf": [float(v) for v in physical],
        "ghi_wm2": [float(v) for v in scenario.ghi_wm2],
        "temp_c": [float(v) for v in scenario.temp_c],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="训练外部光伏容量因子模型")
    parser.add_argument("--train", action="store_true", help="训练并保存模型")
    args = parser.parse_args()
    if not args.train:
        parser.print_help()
        return
    meta = train_and_save()
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
