"""生成机器学习实验 Notebook（02_机器学习光伏迁移.ipynb）。"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "02_机器学习光伏迁移.ipynb"

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 02 机器学习：外部光伏数据训练与 03 数据迁移\n\n"
        "本 Notebook 完成课程要求的“网络数据集 → 训练模型 → 分析教师数据”闭环：\n\n"
        "1. 读取 Kaggle Solar Power Generation 的 Plant 1 发电与气象数据；\n"
        "2. 训练“辐照度/气温 → 光伏容量因子”回归模型；\n"
        "3. 在外部测试集上评估；\n"
        "4. 迁移到教师 03 数据，比较物理折算与 ML 曲线；\n"
        "5. 用两条曲线分别跑基准方案，观察成本与绿电变化。\n\n"
        "> 这是跨区域迁移实验，不代表目标电站的真实功率曲线。"
    ),
    nbf.v4.new_code_cell(
        "from pathlib import Path\n"
        "import sys\n"
        "ROOT = Path.cwd()\n"
        "if not (ROOT / 'src').exists():\n"
        "    ROOT = ROOT.parent\n"
        "sys.path.insert(0, str(ROOT))\n"
        "print('project root:', ROOT)\n"
        "\n"
        "import json\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "\n"
        "from src.ml.pv import (\n"
        "    training_frame, train_and_save, model_info, load_artifact,\n"
        "    compare_on_scenario, apply_to_scenario, FEATURES,\n"
        ")\n"
        "from src.loader import load_scenario_a\n"
        "from src.simulate import SimulationParams, simulate\n"
        "\n"
        "plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']\n"
        "plt.rcParams['axes.unicode_minus'] = False\n"
        "plt.rcParams['figure.dpi'] = 110\n"
        "pd.set_option('display.width', 120)\n"
        "\n"
        "print('模型信息：')\n"
        "print(json.dumps(model_info(), ensure_ascii=False, indent=2)[:1200])"
    ),
    nbf.v4.new_markdown_cell(
        "## 1. 外部训练数据\n\n"
        "如果本地还没有数据，先运行 `python scripts/prepare_external_solar.py`。"
    ),
    nbf.v4.new_code_cell(
        "frame = training_frame()\n"
        "print('形状：', frame.shape)\n"
        "print('时间：', frame['timestamp'].min(), '->', frame['timestamp'].max())\n"
        "frame[['timestamp', 'irradiance_kw_m2', 'ambient_temp_c', 'cf']].head()"
    ),
    nbf.v4.new_code_cell(
        "fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))\n"
        "ax[0].scatter(frame['irradiance_kw_m2'], frame['cf'], s=5, alpha=0.35, color='#f5c451')\n"
        "ax[0].set_xlabel('Irradiance (kW/m2)')\n"
        "ax[0].set_ylabel('PV capacity factor')\n"
        "ax[0].set_title('External plant: irradiance vs CF')\n"
        "ax[1].hist(frame['cf'], bins=30, color='#34d6e8')\n"
        "ax[1].set_xlabel('PV capacity factor')\n"
        "ax[1].set_title('CF distribution')\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell(
        "## 2. 训练与外部测试\n\n"
        "按日期前 80% / 后 20% 时序切分，避免同一小时泄漏。"
    ),
    nbf.v4.new_code_cell(
        "meta = train_and_save()\n"
        "print(json.dumps(meta['metrics'], ensure_ascii=False, indent=2))"
    ),
    nbf.v4.new_code_cell(
        "artifact = load_artifact()\n"
        "model = artifact['model']\n"
        "importance = pd.Series(model.feature_importances_, index=artifact['features']).sort_values()\n"
        "importance.plot(kind='barh', color='#34d6e8', figsize=(6, 3))\n"
        "plt.title('Feature importance')\n"
        "plt.xlabel('Importance')\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell(
        "## 3. 迁移到教师 03 数据\n\n"
        "输入 03 的 GHI 与温度，输出光伏容量因子；与物理折算 `GHI/1000×0.82` 对照。"
    ),
    nbf.v4.new_code_cell(
        "scenario = load_scenario_a()\n"
        "cmp = compare_on_scenario(scenario)\n"
        "summary = {k: v for k, v in cmp.items() if k not in {'timestamps', 'ml_cf', 'physical_cf', 'ghi_wm2', 'temp_c'}}\n"
        "print(json.dumps(summary, ensure_ascii=False, indent=2))"
    ),
    nbf.v4.new_code_cell(
        "# 选 GHI 总量最大的一天展示\n"
        "ts = pd.to_datetime(cmp['timestamps'])\n"
        "ghi = np.array(cmp['ghi_wm2'])\n"
        "df = pd.DataFrame({'ts': ts, 'ghi': ghi})\n"
        "day = df.groupby(df['ts'].dt.date)['ghi'].sum().idxmax()\n"
        "mask = df['ts'].dt.date == day\n"
        "idx = np.where(mask)[0]\n"
        "hours = ts[idx].strftime('%H:%M')\n"
        "\n"
        "plt.figure(figsize=(10, 3.8))\n"
        "plt.plot(hours, np.array(cmp['physical_cf'])[idx], label='Physical CF', color='#f5c451', lw=2)\n"
        "plt.plot(hours, np.array(cmp['ml_cf'])[idx], label='ML CF', color='#34d6e8', lw=2)\n"
        "plt.xticks(range(0, 24, 3))\n"
        "plt.ylabel('Capacity factor')\n"
        "plt.title(f'03 comparison on {day}')\n"
        "plt.legend()\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ),
    nbf.v4.new_markdown_cell(
        "## 4. 用 ML 曲线重跑基准方案\n\n"
        "基准容量 50 MW 风 / 80 MW 光 / 20 MW·80 MWh 储。"
    ),
    nbf.v4.new_code_cell(
        "params = SimulationParams(C_w=50, C_pv=80, C_b=20, E_b=80)\n"
        "base = simulate(scenario, params)\n"
        "ml = simulate(apply_to_scenario(scenario), params)\n"
        "\n"
        "rows = [\n"
        "    ('年化总成本（万元/年）', base.annual_cost / 1e4, ml.annual_cost / 1e4),\n"
        "    ('LCOE（元/kWh）', base.lcoe, ml.lcoe),\n"
        "    ('弃电率', base.curtail_rate, ml.curtail_rate),\n"
        "    ('绿电占比', base.green_ratio, ml.green_ratio),\n"
        "]\n"
        "for name, a, b in rows:\n"
        "    print(f'{name:18s} 物理 {a:10.4f}   ML {b:10.4f}   差 {b-a:+.4f}')"
    ),
    nbf.v4.new_markdown_cell(
        "## 5. 结论与局限\n\n"
        "- 外部测试集 R² 约 0.996、MAE 约 0.0077；迁移到 03 后两条曲线相关系数约 0.9997。\n"
        "- ML 平均 CF 约 0.269，高于物理的 0.234；用 ML 曲线重跑基准方案，年化成本约从 2.13 亿元降到 1.96 亿元。\n"
        "- 外部数据只有 33 天、位于印度，目标数据在江苏沿海；存在域偏移，ML 只作为对照，不作为主结论。\n"
        "- 物理折算 + 规则调度 + PSO/GWO 仍是平台主链路。"
    ),
]
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb.metadata["language_info"] = {"name": "python", "version": "3.14"}
OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, str(OUT))
print(f"written {OUT} ({OUT.stat().st_size} bytes)")
