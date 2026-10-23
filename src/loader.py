"""数据加载与场景构造。

场景 A：03 源荷气象电价（规划输入）。
场景 B：05 风光负荷同步出力（50/80/20/80 基准运行，用于校验/对照）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEVICE, SOURCE_PACKAGE, TARIFF

DATA_DIR = SOURCE_PACKAGE


@dataclass
class ScenarioData:
    name: str
    timestamps: pd.DatetimeIndex
    wind_cf: np.ndarray
    pv_cf: np.ndarray
    load_mw: np.ndarray
    price_buy: np.ndarray
    price_sell: float
    meta: dict = field(default_factory=dict)
    # 原始气象量，供机器学习模型做外部泛化（场景 B 无气象列时为 None）
    ghi_wm2: np.ndarray | None = None
    temp_c: np.ndarray | None = None

    @property
    def hours(self) -> int:
        return len(self.load_mw)


def wind_power_cf(speed_m_s: np.ndarray) -> np.ndarray:
    """风机标幺出力：3 切入、11 额定、25 切出。"""
    v = np.asarray(speed_m_s, dtype=float)
    cf = np.zeros_like(v)
    m = (v >= DEVICE["wind_cut_in_m_s"]) & (v < DEVICE["wind_rated_m_s"])
    cf[m] = (v[m] ** 3 - DEVICE["wind_cut_in_m_s"] ** 3) / (
        DEVICE["wind_rated_m_s"] ** 3 - DEVICE["wind_cut_in_m_s"] ** 3
    )
    m = (v >= DEVICE["wind_rated_m_s"]) & (v <= DEVICE["wind_cut_out_m_s"])
    cf[m] = 1.0
    return np.clip(cf, 0.0, 1.0)


def pv_power_cf(ghi_w_m2: np.ndarray) -> np.ndarray:
    """光伏标幺出力：GHI/1000 × 系统效率。"""
    ghi = np.asarray(ghi_w_m2, dtype=float)
    return np.clip(ghi / 1000.0 * DEVICE["pv_efficiency"], 0.0, 1.0)


def tariff_for_index(index: pd.DatetimeIndex) -> np.ndarray:
    """按 07 华东分时电价映射到小时。

    00–08 谷 0.35；08–17 平 0.75；17–21 峰 1.15；21–24 平 0.75。
    """
    hour = index.hour.to_numpy()
    price = np.full(len(index), TARIFF["flat"], dtype=float)
    price[(hour >= 0) & (hour < 8)] = TARIFF["valley"]
    price[(hour >= 17) & (hour < 21)] = TARIFF["peak"]
    return price


def _read_csv(name: str) -> pd.DataFrame:
    path: Path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在：{path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def load_scenario_a(use_tariff: bool = True) -> ScenarioData:
    """03：规划输入。"""
    df = _read_csv("03_小时级源荷气象电价数据.csv")
    ts = pd.to_datetime(df["时间"], format="mixed")
    df = df.assign(timestamp=ts).set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    wind_cf = wind_power_cf(df["风速(m/s)"].to_numpy())
    ghi = df["总辐照度(W/m2)"].to_numpy(dtype=float)
    temp = df["温度(℃)"].to_numpy(dtype=float)
    pv_cf = pv_power_cf(ghi)
    load = df["有功负荷(MW)"].to_numpy(dtype=float)
    price_raw = df["购电价(元/kWh)"].to_numpy(dtype=float)
    price = tariff_for_index(df.index) if use_tariff else price_raw

    return ScenarioData(
        name="A_03_planning",
        timestamps=df.index,
        wind_cf=wind_cf,
        pv_cf=pv_cf,
        load_mw=load,
        price_buy=price,
        price_sell=TARIFF["sell"],
        meta={
            "source": "03_小时级源荷气象电价数据.csv",
            "rows": int(len(df)),
            "start": str(df.index.min()),
            "end": str(df.index.max()),
            "price_mode": "07_tou" if use_tariff else "03_raw",
            "wind_cf_mean": float(wind_cf.mean()),
            "pv_cf_mean": float(pv_cf.mean()),
            "load_mean_mw": float(load.mean()),
            "load_max_mw": float(load.max()),
            "weather": "GHI + 2m temperature available",
        },
        ghi_wm2=ghi,
        temp_c=temp,
    )


def load_scenario_b(use_tariff: bool = True) -> ScenarioData:
    """05：基准运行；风光按 50/80 MW 归一化为标幺。"""
    df = _read_csv("05_风光负荷同步出力数据.csv")
    ts = pd.to_datetime(df["datetime"], format="mixed")
    df = df.assign(timestamp=ts).set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    wind_cf = np.clip(df["wind_power_MW"].to_numpy(dtype=float) / 50.0, 0.0, 1.0)
    pv_cf = np.clip(df["pv_power_MW"].to_numpy(dtype=float) / 80.0, 0.0, 1.0)
    load = df["load_MW"].to_numpy(dtype=float)
    price_raw = tariff_for_index(df.index) if use_tariff else np.zeros(len(df))
    price = price_raw

    return ScenarioData(
        name="B_05_base",
        timestamps=df.index,
        wind_cf=wind_cf,
        pv_cf=pv_cf,
        load_mw=load,
        price_buy=price,
        price_sell=TARIFF["sell"],
        meta={
            "source": "05_风光负荷同步出力数据.csv",
            "rows": int(len(df)),
            "start": str(df.index.min()),
            "end": str(df.index.max()),
            "base_capacity_mw": {"wind": 50.0, "pv": 80.0},
            "wind_cf_mean": float(wind_cf.mean()),
            "pv_cf_mean": float(pv_cf.mean()),
            "load_mean_mw": float(load.mean()),
            "load_max_mw": float(load.max()),
        },
    )
