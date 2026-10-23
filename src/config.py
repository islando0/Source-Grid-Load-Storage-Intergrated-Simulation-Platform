from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "output"
MODELS_DIR = BASE_DIR / "models"

# 教师数据包（原始文件只读，位于项目 data/raw 下）
SOURCE_PACKAGE = DATA_DIR / "raw" / "源网荷储一体化仿真数据"

PROJECT = {
    "name": "华东沿海工业园源网荷储一体化示范项目",
    "location": "江苏沿海",
    "year": 2026,
    # 基础方案
    "base_capacity_mw": {"wind": 50.0, "pv": 80.0, "battery": 20.0, "battery_mwh": 80.0},
    # 优化参考结果
    "opt_capacity_mw": {"wind": 80.0, "pv": 120.0, "battery": 40.0, "battery_mwh": 160.0, "grid": 70.0},
}

# 成本与电价（来自 08 / 07）
COST = {
    "wind_capex_yuan_per_kw": 6500.0,
    "pv_capex_yuan_per_kw": 3500.0,
    "battery_capex_yuan_per_kwh": 1200.0,
    "discount_rate": 0.08,
    "carbon_price_yuan_per_t": 80.0,
}

TARIFF = {
    "valley": 0.35,
    "flat": 0.75,
    "peak": 1.15,
    "sell": 0.35,
}

DEVICE = {
    "wind_cut_in_m_s": 3.0,
    "wind_rated_m_s": 11.0,
    "wind_cut_out_m_s": 25.0,
    "pv_efficiency": 0.82,
    "battery_efficiency": 0.92,
    "soc_min": 0.10,
    "soc_max": 0.95,
}
