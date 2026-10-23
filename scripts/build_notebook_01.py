"""生成第一个数据分析 Notebook（可重复执行）。"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "01_数据体检与场景对比.ipynb"
OUT.parent.mkdir(parents=True, exist_ok=True)

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

cells = []

cells.append(
    nbf.v4.new_markdown_cell(
        """# 01 数据体检与场景对比

对象：教师数据包 03（场景 A 规划输入）与 05（场景 B 基准运行）。

目标：
1. 检查两份数据的时间轴、缺失、重复、量纲和物理范围；
2. 说明为什么不能把 03/05 按时间行合并；
3. 对比电价、负荷、风光资源；
4. 用同一套仿真器跑 50/80/20/80 基线，给出年化成本、弃电、SOC 指标。

数据只有 2026-01-01—08-31 共 5832 小时，所有“年化”都是按 8760/5832 折算的样本年化。
"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "src").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.loader import load_scenario_a, load_scenario_b
from src.simulate import SimulationParams, simulate

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 30)
print("ROOT =", ROOT)"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """sA = load_scenario_a()
sB = load_scenario_b()
print("A:", sA.name, sA.hours, sA.meta)
print("B:", sB.name, sB.hours, sB.meta)"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 03 原始表：字段、缺失、重复
raw03 = pd.read_csv(ROOT / "data/raw/源网荷储一体化仿真数据/03_小时级源荷气象电价数据.csv", encoding="utf-8-sig")
raw03["时间"] = pd.to_datetime(raw03["时间"], format="mixed")
print("shape", raw03.shape)
print("columns", list(raw03.columns))
print("time", raw03["时间"].min(), "->", raw03["时间"].max())
print("duplicate timestamps", raw03["时间"].duplicated().sum())
print("missing", raw03.isna().sum().to_dict())
raw03.describe().T"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 05 原始表：基准运行结果
raw05 = pd.read_csv(ROOT / "data/raw/源网荷储一体化仿真数据/05_风光负荷同步出力数据.csv", encoding="utf-8-sig")
raw05["datetime"] = pd.to_datetime(raw05["datetime"], format="mixed")
print("shape", raw05.shape)
print("columns", list(raw05.columns))
print("time", raw05["datetime"].min(), "->", raw05["datetime"].max())
print("duplicate timestamps", raw05["datetime"].duplicated().sum())
print("missing", raw05.isna().sum().to_dict())
raw05.describe().T"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 同时间轴对比：只看差异，不做按行合并
cmp = pd.DataFrame({
    "A_load_MW": sA.load_mw,
    "B_load_MW": sB.load_mw,
    "A_wind_cf": sA.wind_cf,
    "B_wind_cf": sB.wind_cf,
    "A_pv_cf": sA.pv_cf,
    "B_pv_cf": sB.pv_cf,
})
print(cmp.describe().T[["mean", "std", "min", "max"]])
print("\\ncorr:")
print(cmp.corr().round(3))"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 03 原始电价 vs 07 分时模板
print("03 原始电价分布:")
print(raw03["购电价(元/kWh)"].value_counts().sort_index().to_string())
print("\\n07 分时模板: 谷 0.35 / 平 0.75 / 峰 1.15 / 上网 0.35")
print("场景 A 使用 07 映射后的分布:")
print(pd.Series(sA.price_buy).value_counts().sort_index().to_string())
print("场景 A 使用 07 映射后的均值:", round(float(sA.price_buy.mean()), 4), "元/kWh")"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 基线 50/80/20/80，两个场景同一仿真器
rows = []
for name, s in (("A", sA), ("B", sB)):
    r = simulate(s, SimulationParams(C_w=50, C_pv=80, C_b=20, E_b=80))
    rows.append({
        "scenario": name,
        "annual_cost_万元": round(r.annual_cost / 1e4, 1),
        "LCOE_元每kWh": round(r.lcoe, 3),
        "curtail_rate": round(r.curtail_rate, 4),
        "green_ratio": round(r.green_ratio, 4),
        "soc_in_band": round(r.soc_in_band_ratio, 4),
        "ens_MWh": round(r.ens_mwh, 3),
        "end_soc": round(r.end_soc, 3),
    })
pd.DataFrame(rows)"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        """# 对照 06 的 80/120/40/160 与“零储能”
rows = []
for label, x in (("06参考 80/120/40/160", (80, 120, 40, 160)), ("零储能 80/120", (80, 120, 0, 0))):
    r = simulate(sA, SimulationParams(*x))
    rows.append({
        "config": label,
        "annual_cost_万元": round(r.annual_cost / 1e4, 1),
        "curtail_rate": round(r.curtail_rate, 4),
        "soc_in_band": round(r.soc_in_band_ratio, 4),
        "lcoe": round(r.lcoe, 3),
    })
pd.DataFrame(rows)"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        """## 结论

- 03 与 05 的时间轴长度相同，但负荷、温度、风速不一致，属于两个场景；不能按时间行合并。
- 03 原始电价只有 0.32/0.45/0.85 三档，和 07 模板的 0.35/0.75/1.15 不一致；模型主口径用 07，03 原始电价留作敏感性。
- 只有 1–8 月，年化按 8760/5832 折算；报告必须写清“样本年化”。
- 同一仿真器下，06 的 80/120/40/160 与 06 文档的 2.85 亿元/3.5% 弃电对不上，原因是 03/05/06 的负荷与资源口径不同，不能把 06 当精确答案。
- 成本优先时零储能可能是经济最优；是否需要强制配储/绿电/弃电约束，需要老师确认。
"""
    )
)

nb["cells"] = cells
nbf.write(nb, OUT)
print("wrote", OUT)
