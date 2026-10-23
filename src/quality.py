"""上传数据体检：时间轴、缺失、重复、异常、物理范围、可用性评分。"""

from __future__ import annotations

import io
import math
import re
from typing import Any

import numpy as np
import pandas as pd

MAX_ROWS = 100_000
MAX_BYTES = 50 * 1024 * 1024

# 原始列名 -> 系统字段。匹配时忽略大小写、空格和常见单位后缀。
ALIASES: dict[str, list[str]] = {
    "timestamp": ["timestamp", "时间", "datetime", "date", "time", "日期"],
    "wind_speed_m_s": ["wind_speed_m_s", "风速(m/s)", "风速", "wind_speed", "ws10m", "ws50m"],
    "ghi_w_m2": ["ghi_w_m2", "总辐照度(w/m2)", "总辐照度", "ghi", "辐照度", "solar"],
    "temp_c": ["temp_c", "temperature_c", "温度(℃)", "温度", "temp", "t2m"],
    "load_mw": ["load_mw", "有功负荷(mw)", "负荷(mw)", "负荷", "load", "building_kw", "building_kw"],
    "pv_mw": ["pv_mw", "pv_kw", "光伏可用出力(mw)", "光伏出力", "pv", "pv_power_mw"],
    "wind_mw": ["wind_mw", "风电出力", "wind_power_mw"],
    "battery_mw": ["battery_mw", "battery_kw", "储能功率"],
    "battery_charge_mw": ["battery_charge_mw", "battery_charge"],
    "battery_discharge_mw": ["battery_discharge_mw", "battery_discharge"],
    "soc": ["soc", "soc_pct", "soc(%)", "soc_pct"],
    "grid_buy_mw": ["grid_buy_mw", "购电", "grid_kw", "feeder_kw"],
    "grid_sell_mw": ["grid_sell_mw", "上网", "grid_sell"],
    "curtail_mw": ["curtail_mw", "curtailment_mw", "弃电", "弃风弃光"],
    "price_buy": ["price_buy", "购电价(元/kwh)", "购电价", "price", "电价"],
    "price_sell": ["price_sell", "上网电价", "sell_price"],
}

NUMERIC_FIELDS = [
    "wind_speed_m_s", "ghi_w_m2", "temp_c", "load_mw", "pv_mw", "wind_mw",
    "battery_mw", "battery_charge_mw", "battery_discharge_mw", "soc",
    "grid_buy_mw", "grid_sell_mw", "curtail_mw", "price_buy", "price_sell",
]

PHYSICAL = {
    "wind_speed_m_s": (0, 50, "风速"),
    "ghi_w_m2": (0, 1500, "辐照度"),
    "temp_c": (-40, 50, "温度"),
    "load_mw": (0, 1e7, "负荷"),
    "pv_mw": (0, 1e6, "光伏出力"),
    "wind_mw": (0, 1e6, "风电出力"),
}


def _norm(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("（", "(")
        .replace("）", ")")
    )


def _match_columns(columns: list[str]) -> dict[str, str]:
    normalized = {_norm(c): c for c in columns}
    mapping: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            key = _norm(alias)
            if key in normalized and normalized[key] not in mapping.values():
                mapping[field] = normalized[key]
                break
    return mapping


def _read_table(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    if lower.endswith(".csv"):
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ValueError(f"CSV 解析失败：{last_error}")
    raise ValueError("只支持 .csv / .xlsx / .xls")


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat(sep=" ")
    return value


def _records(df: pd.DataFrame, n: int = 5) -> list[dict[str, Any]]:
    out = []
    for row in df.head(n).to_dict(orient="records"):
        out.append({k: _to_jsonable(v) for k, v in row.items()})
    return out


def inspect_bytes(filename: str, content: bytes) -> dict[str, Any]:
    if len(content) > MAX_BYTES:
        raise ValueError("文件超过 50 MB 限制")

    df = _read_table(filename, content)
    if len(df) > MAX_ROWS:
        raise ValueError(f"行数超过 {MAX_ROWS} 限制")
    if len(df) < 2:
        raise ValueError("数据行数过少，至少需要 2 行")

    mapping = _match_columns([str(c) for c in df.columns])
    time_col = mapping.get("timestamp")
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # 时间轴
    time_info: dict[str, Any] = {"column": time_col}
    ts = None
    invalid_ts = 0
    interval_min: float | None = None
    coverage = 0.0
    gaps = 0

    if not time_col:
        blocking.append({"code": "NO_TIME_COLUMN", "message": "未找到时间列，请手动映射 timestamp"})
    else:
        raw = df[time_col]
        ts = pd.to_datetime(raw, errors="coerce", format="mixed")
        invalid_ts = int(ts.isna().sum())
        first_raw = str(raw.dropna().iloc[0]).strip() if raw.notna().any() else ""
        time_only = bool(re.match(r"^\d{1,2}:\d{2}", first_raw))
        if time_only:
            time_info["time_only"] = True
            warnings.append({
                "code": "TIME_ONLY",
                "message": "时间列只有时刻没有日期，按典型日处理，不能用于全年指标",
            })
        if invalid_ts / len(df) > 0.05:
            blocking.append({
                "code": "TIME_PARSE_FAILED",
                "count": invalid_ts,
                "message": f"{invalid_ts} 行时间无法解析，超过 5%",
            })
        elif invalid_ts:
            warnings.append({
                "code": "INVALID_TIMESTAMP",
                "count": invalid_ts,
                "message": f"{invalid_ts} 行时间无法解析，可在清洗时修复或剔除",
            })

        valid = ts.dropna().sort_values()
        if len(valid) >= 2:
            diffs = valid.diff().dropna().dt.total_seconds() / 60
            diffs = diffs[diffs > 0]
            if len(diffs):
                interval_min = float(diffs.mode().iloc[0])
            start, end = valid.iloc[0], valid.iloc[-1]
            time_info.update({
                "start": start.isoformat(sep=" "),
                "end": end.isoformat(sep=" "),
                "interval_minutes": interval_min,
            })
            if interval_min and interval_min not in (5, 10, 15, 30, 60):
                blocking.append({
                    "code": "UNSUPPORTED_INTERVAL",
                    "message": f"时间间隔 {interval_min:g} 分钟，暂支持 5/10/15/30/60",
                })
            if interval_min:
                expected = int((end - start).total_seconds() / 60 / interval_min) + 1
                unique_valid = valid.drop_duplicates().shape[0]
                coverage = min(1.0, unique_valid / max(expected, 1))
                gaps = int((diffs > interval_min * 1.5).sum())
                time_info["coverage"] = round(coverage, 4)
                time_info["expected_rows"] = expected
                time_info["valid_rows"] = int(unique_valid)
            span_days = (end - start).total_seconds() / 86400
            if span_days < 300 and not time_only:
                warnings.append({
                    "code": "PARTIAL_PERIOD",
                    "message": f"仅覆盖 {span_days:.0f} 天，年指标需标注为期间值或年化估算",
                })
        else:
            blocking.append({"code": "NO_VALID_TIME", "message": "没有可用的时间点"})

    # 缺失
    missing = {str(c): int(df[c].isna().sum()) for c in df.columns}
    missing_ratio = {k: v / len(df) for k, v in missing.items()}
    key_fields = [f for f in ("load_mw", "wind_speed_m_s", "ghi_w_m2", "pv_mw") if f in mapping]
    key_missing = {mapping[f]: missing_ratio[mapping[f]] for f in key_fields}
    worst_key = max(key_missing.values()) if key_missing else 0.0
    if worst_key > 0.30:
        blocking.append({
            "code": "KEY_COLUMN_MISSING",
            "message": f"关键列缺失率 {worst_key:.1%}，超过 30%",
        })
    elif worst_key > 0.05:
        warnings.append({
            "code": "MISSING_VALUES",
            "message": f"关键列缺失率最高 {worst_key:.1%}",
        })

    # 重复
    duplicates = 0
    if ts is not None:
        duplicates = int(ts.dropna().duplicated().sum())
        ratio = duplicates / len(df)
        if ratio > 0.05:
            blocking.append({"code": "DUPLICATE_TIMESTAMP", "count": duplicates, "message": "重复时间戳超过 5%"})
        elif duplicates:
            warnings.append({"code": "DUPLICATE_TIMESTAMP", "count": duplicates, "message": "存在重复时间戳，导入时保留最后一条"})

    # 物理范围
    physical_issues: list[dict[str, Any]] = []
    for field, (low, high, label) in PHYSICAL.items():
        col = mapping.get(field)
        if not col:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        bad = int(((values < low) | (values > high)).sum())
        if bad:
            physical_issues.append({
                "code": f"{field.upper()}_OUT_OF_RANGE",
                "column": col,
                "count": bad,
                "message": f"{label}超出 {low}–{high} 范围",
            })

    soc_col = mapping.get("soc")
    if soc_col:
        soc = pd.to_numeric(df[soc_col], errors="coerce")
        upper = 1.5 if soc.max(skipna=True) <= 1.5 else 100.0
        bad = int(((soc < 0) | (soc > upper)).sum())
        if bad:
            physical_issues.append({
                "code": "SOC_OUT_OF_RANGE",
                "column": soc_col,
                "count": bad,
                "message": f"SOC 超出 0–{upper:g} 范围",
            })

    for item in physical_issues:
        warnings.append(item)

    # 负出力（夜间光伏等）
    for field in ("pv_mw", "wind_mw"):
        col = mapping.get(field)
        if col:
            values = pd.to_numeric(df[col], errors="coerce")
            bad = int((values < 0).sum())
            if bad:
                warnings.append({
                    "code": "NEGATIVE_GENERATION",
                    "column": col,
                    "count": bad,
                    "message": f"{col} 存在 {bad} 个负值，建议置零或标记",
                })

    # 平衡校验（05 类数据）：风光 + 储放 + 购电 = 负荷 + 储充 + 上网 + 弃电
    balance_fields = ["wind_mw", "pv_mw", "load_mw"]
    if all(f in mapping for f in balance_fields):
        supply = pd.to_numeric(df[mapping["wind_mw"]], errors="coerce").fillna(0) + \
                 pd.to_numeric(df[mapping["pv_mw"]], errors="coerce").fillna(0)
        demand = pd.to_numeric(df[mapping["load_mw"]], errors="coerce").fillna(0)

        if "grid_buy_mw" in mapping:
            supply += pd.to_numeric(df[mapping["grid_buy_mw"]], errors="coerce").fillna(0)
        if "grid_sell_mw" in mapping:
            demand += pd.to_numeric(df[mapping["grid_sell_mw"]], errors="coerce").fillna(0)
        if "curtail_mw" in mapping:
            demand += pd.to_numeric(df[mapping["curtail_mw"]], errors="coerce").fillna(0)

        if "battery_discharge_mw" in mapping:
            supply += pd.to_numeric(df[mapping["battery_discharge_mw"]], errors="coerce").fillna(0)
        if "battery_charge_mw" in mapping:
            demand += pd.to_numeric(df[mapping["battery_charge_mw"]], errors="coerce").fillna(0)
        elif "battery_mw" in mapping:
            # 约定：battery_mw 正为放电、负为充电
            supply += pd.to_numeric(df[mapping["battery_mw"]], errors="coerce").fillna(0)

        err = (supply - demand).abs()
        max_err = float(err.max()) if len(err) else 0.0
        mean_load = float(demand.mean()) if len(demand) else 0.0
        if mean_load and max_err / mean_load > 0.01:
            warnings.append({
                "code": "BALANCE_MISMATCH",
                "message": f"功率平衡最大误差 {max_err:.2f} MW，超过平均负荷的 1%",
            })

    # 异常值（IQR 三倍）
    outliers: dict[str, int] = {}
    for field in NUMERIC_FIELDS:
        col = mapping.get(field)
        if not col:
            continue
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(values) < 10:
            continue
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        count = int(((values < q1 - 3 * iqr) | (values > q3 + 3 * iqr)).sum())
        if count:
            outliers[col] = count

    # 评分
    missing_total = sum(missing.values())
    missing_ratio_all = missing_total / (len(df) * max(len(df.columns), 1))
    outlier_count = sum(outliers.values())
    invalid_ratio = invalid_ts / len(df)
    dup_ratio = duplicates / len(df)
    physical_count = sum(item["count"] for item in physical_issues)

    score = 100.0
    score -= min(20.0, invalid_ratio * 200)
    score -= min(15.0, dup_ratio * 200)
    score -= min(20.0, missing_ratio_all * 150)
    score -= min(15.0, gaps * 2)
    score -= min(10.0, (outlier_count / max(len(df), 1)) * 100)
    score -= min(20.0, physical_count * 3)
    score = int(round(max(0.0, score)))

    if blocking:
        status = "unusable"
    elif warnings:
        status = "usable_with_warnings"
    else:
        status = "usable"

    return {
        "filename": filename,
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "mapping": mapping,
        "unmapped": [str(c) for c in df.columns if str(c) not in mapping.values()],
        "time": time_info,
        "missing": missing,
        "duplicates": duplicates,
        "gaps": gaps,
        "outliers": outliers,
        "physical_issues": physical_issues,
        "score": score,
        "status": status,
        "blocking": blocking,
        "warnings": warnings,
        "preview": _records(df),
    }
