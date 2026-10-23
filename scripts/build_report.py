"""Generate docs/实验报告.docx from the course template.

The template cover and section layout are preserved; the body is rebuilt from
project results so the report can be regenerated after data/model changes.

Run:
    python scripts/build_report.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".tmp" / "实验报告模板.docx"
OUTPUT = ROOT / "docs" / "实验报告.docx"
SHOTS = ROOT / "docs" / "screenshots"

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
LATIN_FONT = "Times New Roman"
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)


def set_run_font(run, name: str = BODY_FONT, size: float = 11.5, bold: bool = False,
                 color: RGBColor | None = None, italic: bool = False) -> None:
    run.font.name = LATIN_FONT if name == BODY_FONT else name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def style_font(style, name: str, size: float, bold: bool = False,
               color: RGBColor | None = None) -> None:
    style.font.name = LATIN_FONT if name == BODY_FONT else name
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), LATIN_FONT)
    style.font.size = Pt(size)
    style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color


def shade(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def cell_margins(table, top=40, bottom=40, left=80, right=80) -> None:
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for tag, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tbl_pr.append(mar)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), "A6A6A6")
        borders.append(node)
    tbl_pr.append(borders)


def add_body(doc, text: str, first_indent: bool = True,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY) -> None:
    p = doc.add_paragraph(style="ReportBody")
    p.alignment = align
    p.paragraph_format.first_line_indent = Pt(23) if first_indent else Pt(0)
    run = p.add_run(text)
    set_run_font(run, BODY_FONT, 11.5)


def add_lead(doc, lead: str, text: str) -> None:
    p = doc.add_paragraph(style="ReportBody")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Pt(23)
    r1 = p.add_run(lead)
    set_run_font(r1, BODY_FONT, 11.5, bold=True, color=ACCENT)
    r2 = p.add_run(text)
    set_run_font(r2, BODY_FONT, 11.5)


def add_item(doc, text: str, marker: str = "•") -> None:
    p = doc.add_paragraph(style="ReportBody")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Cm(0.74)
    p.paragraph_format.first_line_indent = Cm(-0.74)
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run(f"{marker} ")
    set_run_font(r1, BODY_FONT, 11, bold=True, color=ACCENT)
    r2 = p.add_run(text)
    set_run_font(r2, BODY_FONT, 11)


def add_h1(doc, text: str) -> None:
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, HEAD_FONT, 16, bold=True, color=RGBColor(0, 0, 0))


def add_h2(doc, text: str) -> None:
    p = doc.add_paragraph(style="Heading 2")
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, HEAD_FONT, 13.5, bold=True, color=ACCENT)


def add_formula(doc, text: str) -> None:
    p = doc.add_paragraph(style="ReportBody")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(5)
    run = p.add_run(text)
    set_run_font(run, "Cambria Math", 10.5, color=RGBColor(0x22, 0x22, 0x22))


def add_caption(doc, text: str) -> None:
    p = doc.add_paragraph(style="ReportCaption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_run_font(run, BODY_FONT, 9.5, color=RGBColor(0x55, 0x55, 0x55))


def add_table(doc, headers, rows, widths=None, font_size: float = 9.2,
              caption: str | None = None, first_col_left: bool = True) -> None:
    if caption:
        add_caption(doc, caption)
    table = doc.add_table(rows=1, cols=len(headers))
    if "Table Grid" not in [s.name for s in doc.styles]:
        doc.styles.add_style("Table Grid", WD_STYLE_TYPE.TABLE)
    table.style = "Table Grid"
    table_borders(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell_margins(table)
    header_row = table.rows[0]
    repeat_header(header_row)
    for i, text in enumerate(headers):
        cell = header_row.cells[i]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade(cell, "DCE6F1")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(str(text))
        set_run_font(run, HEAD_FONT, font_size, bold=True)
        if widths:
            cell.width = Cm(widths[i])
    for row in rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            cell = cells[i]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if (i == 0 and first_col_left) else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(text))
            set_run_font(run, BODY_FONT, font_size)
            if widths:
                cell.width = Cm(widths[i])
    p = doc.add_paragraph(style="ReportBody")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = Pt(0)


def add_figure(doc, path: Path, caption: str, width_cm: float = 14.2) -> None:
    if not path.exists():
        add_body(doc, f"（图缺失：{path.name}）", first_indent=False)
        return
    p = doc.add_paragraph(style="ReportBody")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    add_caption(doc, caption)


def add_page_break(doc) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run()
    run.add_break(WD_BREAK.PAGE)


def setup_styles(doc) -> None:
    from docx.enum.style import WD_STYLE_TYPE

    normal = doc.styles["Normal"]
    style_font(normal, BODY_FONT, 11)
    normal.paragraph_format.line_spacing = 1.15

    body = doc.styles.add_style("ReportBody", WD_STYLE_TYPE.PARAGRAPH)
    body.base_style = doc.styles["Normal"]
    style_font(body, BODY_FONT, 11.5)
    body.paragraph_format.line_spacing = 1.5
    body.paragraph_format.space_before = Pt(0)
    body.paragraph_format.space_after = Pt(3)
    body.paragraph_format.widow_control = True

    cap = doc.styles.add_style("ReportCaption", WD_STYLE_TYPE.PARAGRAPH)
    cap.base_style = doc.styles["Normal"]
    style_font(cap, BODY_FONT, 9.5)
    cap.paragraph_format.line_spacing = 1.0
    cap.paragraph_format.keep_with_next = True

    h1 = doc.styles["Heading 1"]
    style_font(h1, HEAD_FONT, 16, bold=True, color=RGBColor(0, 0, 0))
    h1.paragraph_format.space_before = Pt(18)
    h1.paragraph_format.space_after = Pt(10)
    h1.paragraph_format.keep_with_next = True

    h2 = doc.styles["Heading 2"] if "Heading 2" in [s.name for s in doc.styles] else doc.styles.add_style("Heading 2", WD_STYLE_TYPE.PARAGRAPH)
    h2.base_style = doc.styles["Heading 1"]
    style_font(h2, HEAD_FONT, 13.5, bold=True, color=ACCENT)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(5)
    h2.paragraph_format.keep_with_next = True


# ---------------------------------------------------------------------------
# 内容
# ---------------------------------------------------------------------------

def build() -> None:
    doc = Document(TEMPLATE)
    setup_styles(doc)

    # 封面：题目、日期；班级/姓名/学号保留模板横线，提交前由学生手填。
    cover_title = doc.paragraphs[13]
    if len(cover_title.runs) >= 11:
        cover_title.runs[5].text = "实验九　源网荷储一体化仿真平台"
        for run in cover_title.runs[6:]:
            run.text = ""
        set_run_font(cover_title.runs[5], BODY_FONT, 15, bold=False)

    date_p = doc.paragraphs[19]
    for run in date_p.runs:
        run.text = ""
    r = date_p.add_run("2026 年 10 月")
    set_run_font(r, BODY_FONT, 14)

    # 保留封面与两个 section；删除模板正文中的五个空标题，重建正文。
    for p in list(doc.paragraphs)[20:]:
        p._element.getparent().remove(p._element)

    # 正文首次出现时使用模板第二 section；若模板只剩一个 section，补一个分页。
    if len(doc.sections) == 1:
        doc.add_section(WD_SECTION.NEW_PAGE)

    # ---------------------------- 一、实验目的 ----------------------------
    add_h1(doc, "一、实验目的")
    add_body(doc, "在“双碳”目标和新型电力系统建设背景下，园区级源网荷储一体化系统需要在有限的外网通道条件下，"
                  "协调风电、光伏、储能和负荷的时序关系。系统的规划配置不能只看装机规模，还要回答三个问题："
                  "数据是否可信、给定容量下系统如何运行、容量配到多大在经济性与友好性之间更合适。")
    add_body(doc, "本实验以江苏沿海某工业园区的源网荷储项目为对象，读取小时级风速、总辐照度、温度、负荷和分时电价数据，"
                  "完成数据体检、逐时功率平衡仿真、PSO/GWO 容量优化、外部公开数据训练的机器学习迁移，以及 Vue3 + FastAPI 的可视化实现。"
                  "实验的重点不是单独做一个大屏，而是把数据质量、时序仿真、优化计算和结果表达串成一条可复现的链路。")
    add_body(doc, "具体目标如下：")
    add_item(doc, "掌握用 Pandas/NumPy 完成时间序列读取、时间解析、缺失与重复处理、物理范围检查和描述性统计的方法。")
    add_item(doc, "建立含风电、光伏、储能、外网购电、弃电、失负荷和 SOC 的逐时功率平衡模型。")
    add_item(doc, "把风电、光伏、储能容量作为决策变量，构造年化总成本目标函数，并用 PSO/GWO 求解。")
    add_item(doc, "用公开光伏数据训练容量因子模型，迁移到本项目数据，评价机器学习口径与物理口径的差异。")
    add_item(doc, "用 FastAPI 提供数据体检、仿真、优化、机器学习接口，用 Vue3 + ECharts 完成运行总览、数据管理、容量优化和报告输出。")
    add_item(doc, "形成包含数据、模型、算法、结果、界面和复现命令的实验报告。")

    # ---------------------------- 二、实验要求 ----------------------------
    add_h1(doc, "二、实验要求")
    add_h2(doc, "2.1 实验环境")
    add_body(doc, "实验在 Windows 本机完成，使用 Anaconda 提供的 Python 解释器和独立虚拟环境，前端使用 Node.js 工具链。"
                  "主要软件与库的版本如下表所示。")
    add_table(doc, ["类别", "工具 / 版本", "用途"], [
        ["编程语言", "Python 3.14.6（Anaconda）", "数据分析、仿真、优化、后端"],
        ["数据分析", "NumPy 2.4.6 / Pandas 3.0.3", "数组运算、时间序列、描述性统计"],
        ["科学计算", "SciPy 1.18.0（HiGHS）", "线性规划求解器储备"],
        ["机器学习", "scikit-learn 1.9.0 / joblib", "随机森林训练、模型持久化"],
        ["后端", "FastAPI 0.115.14 / Uvicorn", "REST API、静态资源托管"],
        ["前端", "Vue 3.5 / Vite 6.4 / ECharts 5.6", "单页应用、交互图表"],
        ["运行环境", "Node.js 24.22 / npm 11.19", "前端依赖安装与构建"],
        ["分析记录", "Jupyter Notebook 7.5", "数据体检与机器学习过程记录"],
        ["测试", "pytest", "27 个自动化测试"],
    ], widths=[2.3, 7.0, 5.1], caption="表 2-1  实验环境与主要工具")
    add_body(doc, "项目采用“后端计算 + 前端展示”的结构：后端在本机 8000 端口同时提供 API 和前端构建产物，"
                  "前端开发时由 Vite 将 /api 代理到后端。这样答辩现场只需启动一个进程即可访问完整系统。")

    add_h2(doc, "2.2 数据与功能要求")
    add_body(doc, "实验数据为项目提供的数据包，包含项目基础数据、设备参数、小时级源荷气象电价、15 分钟典型日、"
                  "基准运行结果、容量优化参考、分时电价、成本参数和数据说明等文件。要求完成：")
    add_item(doc, "数据接入：支持 CSV/XLSX 上传，识别时间列和关键字段，给出时间轴、缺失、重复、物理范围检查结果。")
    add_item(doc, "描述性分析：统计风速、辐照度、温度、负荷、电价的均值、标准差、分位数和月度电量，为场景构造提供依据。")
    add_item(doc, "运行仿真：给定容量后逐时计算功率平衡、储能充放电、SOC、购电、售电、弃电和失负荷。")
    add_item(doc, "容量优化：以年化总成本为目标，输出风电、光伏、储能功率和储能容量的优化结果。")
    add_item(doc, "机器学习：使用网络公开数据训练模型，再迁移到本项目数据做对照分析。")
    add_item(doc, "可视化与报告：页面可交互，报告可下载 HTML 并打印为 PDF。")
    add_body(doc, "数据要求特别强调“不静默合并”：不同文件之间的负荷、资源口径不一致时，应分别建模并在结果中标注来源，"
                  "不能为了凑齐 8760 行而按时间行强行拼接。")

    add_h2(doc, "2.3 技术路线与提交物")
    add_body(doc, "技术路线为“数据体检 → 场景构造 → 逐时仿真 → 容量优化 → 机器学习对照 → API/可视化 → 报告”。"
                  "其中数据体检和场景构造是前置条件，仿真器是优化器的评价函数，优化器只负责搜索容量，不重复实现功率平衡。")
    add_body(doc, "提交物包括：可运行的 Python 后端与 Vue3 前端、数据与模型文件、27 个自动化测试、"
                  "Jupyter Notebook 分析记录、项目实现说明、答辩说明、展示说明，以及本实验报告。")

    # ---------------------------- 三、实验内容 ----------------------------
    add_h1(doc, "三、实验内容")
    add_h2(doc, "3.1 总体技术路线")
    add_body(doc, "系统分为数据层、计算层、服务层和展示层。数据层读取原始 CSV/XLSX，统一字段、时间轴和电价口径；"
                  "计算层由 loader、quality、simulate、optimize 和 ml/pv 五个模块组成；服务层用 FastAPI 暴露接口并把运行摘要写入 SQLite；"
                  "展示层用 Vue3 单页应用组织运行总览、数据管理、机器学习、容量优化和报告输出五个页面。")
    add_body(doc, "一次完整的计算从场景加载开始：load_scenario_a() 把风速折算为风电容量因子，把 GHI 折算为光伏容量因子；"
                  "simulate() 在给定容量下逐时调度并计算年化成本；optimize() 把 simulate() 作为黑箱评价函数，用 PSO/GWO 搜索容量；"
                  "最后把指标和时序返回前端，报告页按场景和方案生成可打印文档。机器学习模块独立训练、独立推理，只作为光伏容量因子的对照口径。")

    add_h2(doc, "3.2 数据来源与字段")
    add_body(doc, "项目数据包共 10 个文件。与本实验主计算直接相关的是 03、05、06、07、08 五个文件，"
                  "01/02 提供基础容量和设备参数，04 是 15 分钟典型日，09 是草稿，10 是数据说明。各文件的角色见表 3-1。")
    add_table(doc, ["文件", "主要内容", "在系统中的角色"], [
        ["03_小时级源荷气象电价数据.csv", "2026-01-01—08-31，5832 行；风速、GHI、温度、负荷、购电价", "场景 A：规划输入，优化主数据"],
        ["05_风光负荷同步出力数据.csv", "5832 行；50/80/20/80 基准运行的风、光、负荷、储能、购电、SOC", "场景 B：基准运行，对照/校验"],
        ["06_容量优化与评价结果.xlsx", "参考容量 80/120/40/160/70 与指标", "参考方案，不作为精确真值"],
        ["07_华东分时电价数据.xlsx", "谷 0.35、平 0.75、峰 1.15、上网 0.35 元/kWh", "统一电价口径"],
        ["08_经济成本参数.xlsx", "风 6500、光 3500、储 1200 元/kWh；折现 8%；碳价 80 元/t", "成本参数"],
        ["01_项目基础数据.xlsx", "基础容量 50/80/20/80 MW", "初始方案"],
        ["02_设备技术参数.xlsx", "切入 3、额定 11 m/s；PV 效率 0.82；储能效率 0.92；SOC 10%—95%", "设备参数"],
        ["04_典型日15分钟运行曲线.csv", "96 点，仅光伏与负荷", "展示/抽样参考"],
        ["09_容量配置及评价指标.xlsx", "130 MW / 80 MWh / 100% 草稿", "与 06 冲突，不采信"],
        ["10_数据说明.docx", "字段与平衡式说明", "口径参考"],
    ], widths=[4.4, 7.0, 3.0], font_size=8.6, caption="表 3-1  数据文件与角色")

    add_body(doc, "03 是场景 A 的主输入，共 5832 行、6 列，时间范围为 2026-01-01 00:00 至 2026-08-31 23:00；"
                  "风速 3—9 m/s，总辐照度 0—900 W/m²，温度 14—26 ℃，负荷 40—56 MW，购电价 0.32/0.45/0.85 元/kWh。"
                  "描述性统计见表 3-2。负荷均值 48.39 MW，中位数 50.49 MW，月度电量约 32.5—36.1 GWh，整体比较平稳。")
    add_table(doc, ["变量", "均值", "标准差", "最小值", "中位数", "最大值"], [
        ["风速 (m/s)", "6.01", "1.50", "3.00", "6.07", "9.00"],
        ["总辐照度 (W/m²)", "284.84", "348.41", "0.00", "0.00", "900.00"],
        ["温度 (℃)", "19.95", "3.46", "14.00", "19.90", "26.00"],
        ["有功负荷 (MW)", "48.39", "5.27", "40.00", "50.49", "56.00"],
        ["购电价 (元/kWh)", "0.44", "0.19", "0.32", "0.32", "0.85"],
    ], widths=[3.7, 2.1, 2.1, 2.1, 2.1, 2.1], caption="表 3-2  场景 A 主要变量的描述性统计")
    add_body(doc, "辐照度中位数为 0，是因为夜间小时占了一半；这不是缺失，而是光伏出力的自然特征。"
                  "这类“零值大量存在”的分布提示后续不能直接用 Z-score 判断异常，必须结合物理范围和时间上下文。")

    add_h2(doc, "3.3 数据体检与清洗")
    add_body(doc, "src/quality.py 的 inspect_bytes() 对上传的 CSV/XLSX 做规则化体检，流程为：读取文件并识别列映射；"
                  "解析时间列、排序、去重；计算采样间隔、理论行数、有效行数和覆盖率；统计缺失、重复、缺口；"
                  "按物理范围检查风速、GHI、温度、负荷、SOC 等；最后给出评分、状态、阻断项和提示项。"
                  "评分不是“越接近 100 越好”的装饰，而是决定数据能否进入计算的阈值。")
    add_body(doc, "对 03 文件的体检结果为：5832 行、6 列，采样间隔 60 min，覆盖率 100%，重复 0，缺口 0，"
                  "评分 90，状态 usable_with_warnings，无阻断项；提示项为 PARTIAL_PERIOD：仅覆盖 243 天，"
                  "年指标需要标注为期间值或年化估算。购电价有 972 个“离群”小时，原因是电价只有 0.32/0.45/0.85 三档，"
                  "统计规则把非众数档识别为离群，并不是数据错误；系统将其作为提示而非阻断，避免误删峰段电价。")
    add_body(doc, "数据包还存在跨文件的口径冲突，处理原则见表 3-3。核心是“分场景、不合并、参考值不当真值”。")
    add_table(doc, ["冲突", "影响", "处理"], [
        ["03 与 05 的负荷、温度、风速不逐行一致", "不能把两份数据按时间行拼接", "分别构造场景 A/B，独立计算"],
        ["03 原始电价 0.32/0.45/0.85 与 07 模板 0.35/0.75/1.15 不一致", "直接使用会改变成本结果", "统一用 07 分时模板，03 原价做敏感性对照"],
        ["04 典型日只有光伏和负荷，没有风电", "不能代表完整源网荷储运行", "只做展示/抽样，不用于优化主计算"],
        ["05 弃电为 0，06 参考弃电率 3.5%", "两套结果不能直接对比", "06 只做参考，不当作同一场景真值"],
        ["06 容量 80/120/40/160 与 09 草稿 130 MW/80 MWh 不一致", "参考方案不唯一", "06 作对照，09 不采信"],
        ["只有 1—8 月，共 5832 h", "不是完整年", "按 8760/5832 年化，并明确标注"],
    ], widths=[5.4, 4.7, 4.2], font_size=8.8, caption="表 3-3  数据冲突与处理原则")

    add_h2(doc, "3.4 场景构造与容量因子")
    add_body(doc, "场景 A 由 load_scenario_a() 构造：按中文列名读取 03，使用 Pandas 解析时间并排序去重；"
                  "风速按风机分段函数折算容量因子，光伏按 GHI/1000×0.82 折算并裁剪到 [0,1]；"
                  "电价按小时映射 07 模板：00—08 时为谷段 0.35，08—17 时为平段 0.75，17—21 时为峰段 1.15，21—24 时回到平段；"
                  "上网电价统一为 0.35 元/kWh。场景 B 读取 05 的风、光、负荷，按 50 MW、80 MW 基准容量归一化为容量因子。")
    add_formula(doc, "CF_w(v) = 0（v < 3 或 v > 25）；CF_w(v) = (v³ − 3³) / (11³ − 3³)（3 ≤ v < 11）；CF_w(v) = 1（11 ≤ v ≤ 25）")
    add_formula(doc, "CF_pv = clip(GHI / 1000 × 0.82, 0, 1)")
    add_body(doc, "式中 v 为轮毂高度风速，3 m/s 为切入风速，11 m/s 为额定风速，25 m/s 为切出风速；"
                  "0.82 为光伏系统综合效率。上述折算把“气象/资源”转换为“单位装机出力”，使优化器可以在 0—300 MW 范围内搜索容量。")

    add_h2(doc, "3.5 仿真模型")
    add_body(doc, "决策变量为 x = [C_w, C_pv, C_b, E_b]，分别表示风电容量、光伏容量、储能功率和储能容量，单位分别为 MW、MW、MW、MWh。"
                  "边界为 0—300、0—300、0—150、0—600；储能时长限制为 2—6 h；外网通道固定 70 MW。")
    add_body(doc, "目标函数为年化总成本最小：")
    add_formula(doc, "min J = C_ann + C_om + C_grid − R_export + C_carbon + λ_cur E_cur + λ_soc E_soc + λ_end E_end")
    add_body(doc, "其中 C_ann = CRF(8%, 25) × CAPEX，CRF = i(1+i)^N / ((1+i)^N − 1)；"
                  "CAPEX = 6500×1000×C_w + 3500×1000×C_pv + 1200×1000×E_b（元）；C_om 取 CAPEX 的 1.5%；"
                  "C_grid 为逐时购电成本；R_export 为上网收入；C_carbon = 0.5703×80×外网购电量；"
                  "λ_cur = 0.05 元/kWh，λ_soc = 0.10 元/kWh，λ_end = 50 元/kWh。失负荷在主模型中按硬约束处理，"
                  "优化适应度中另加 10⁷ 元/MWh 的高惩罚。")
    add_body(doc, "逐时功率平衡为：")
    add_formula(doc, "P_wind,t + P_pv,t + P_dis,t + G_buy,t + E_ens,t = L_t + P_ch,t + G_sell,t + E_cur,t")
    add_body(doc, "式中所有功率单位为 MW，时间步长为 1 h，因此功率数值等于该小时电量（MWh）；E_ens 为失负荷，E_cur 为弃风弃光。"
                  "规则调度按“风光优先供负荷”执行：新能源富余时，先给储能充电，再上网，超过 70 MW 的部分弃电；"
                  "新能源不足时，谷段（电价 ≤ 0.40）允许电网优先供负荷、剩余通道给储能充电至 SOC 80%，其余时段先放储能、再购电、最后才失负荷。"
                  "储能 SOC 更新为：")
    add_formula(doc, "SOC(t+1) = SOC(t) + η P_ch,t Δt / E_b − P_dis,t Δt / (η E_b)")
    add_body(doc, "SOC 硬安全边界为 10%—95%，软目标区间为 30%—80%，越界电量按 0.10 元/kWh 计罚；初始 SOC 为 55%，"
                  "末期偏离 55% 的部分按 50 元/kWh 计罚。零储能时 SOC 指标不适用，系统将其显示为“—”，而不是按 100% 处理。")
    add_body(doc, "仿真输出包括年化总成本、LCOE、弃电率、绿电占比、供电可靠率、SOC 软区间占比、失负荷电量、购售电量、"
                  "弃风弃光电量和完整时序。年化口径为：周期变量成本 × 8760/5832，再加上年化固定成本；"
                  "LCOE 用年化成本除以年化负荷电量，并换算为元/kWh。")

    add_h2(doc, "3.6 优化算法")
    add_body(doc, "容量优化是四维、非线性、带规则分支的黑箱问题。每评估一个候选容量，都要跑一遍 5832 小时调度，"
                  "因此不适合枚举，也不适合直接求梯度。本实验实现 PSO（粒子群）和 GWO（灰狼）两种启发式算法，"
                  "并加入修复算子保证可行性。适应度为：")
    add_formula(doc, "fitness = C_annual + 10⁷ × E_ens + 10⁶ × V_duration")
    add_body(doc, "PSO 的速度和位置更新为：")
    add_formula(doc, "v_i(k+1) = w v_i(k) + c1 r1 (pbest_i − x_i(k)) + c2 r2 (gbest − x_i(k))")
    add_formula(doc, "x_i(k+1) = x_i(k) + v_i(k+1)")
    add_body(doc, "惯性权重 w 从 0.9 线性降到 0.4，c1 = c2 = 1.5，初始粒子在边界内均匀采样。"
                  "GWO 用 α、β、δ 三只头狼引导，D = |C·X_p − X|，X' = X_p − A·D，A = 2a r1 − a，C = 2r2，"
                  "收敛因子 a 从 2 线性降到 0；每只狼向三只头狼移动后取平均。")
    add_body(doc, "修复算子 repair(x) 做四件事：把四个容量裁剪到边界；若 C_b=0 且 E_b>0，则把 C_b 设为 E_b/4；"
                  "若 C_b>0 且 E_b=0，则把 E_b 设为 2C_b；最后把 E_b 限制在 [2C_b, 6C_b] 与 [0,600] 的交集。"
                  "这样可避免 GWO 早期出现“有储能容量但没有功率”的不可行解。单次仿真约 20 ms；30 粒子 × 30 代共 900 次评估，"
                  "在普通笔记本上约 20 分钟，因此答辩现场使用预计算参考结果。")

    add_h2(doc, "3.7 机器学习迁移")
    add_body(doc, "按照“选用网络数据集训练模型，再分析给定数据”的要求，本实验选择 Kaggle 的 Solar Power Generation Data（Ani Kannal），"
                  "使用 Plant 1 的 15 分钟级发电与气象数据。发电文件 68,778 行、22 台逆变器，气象文件 3,182 行；"
                  "按时间聚合逆变器 AC 功率，峰值约 29.15 MW，按 30 MW 装机假设归一化为容量因子。"
                  "原始日期格式为 dd-mm-yyyy，解析时必须使用 dayfirst=True，否则会产生错误的时间顺序。")
    add_body(doc, "模型输入为辐照度、环境温度和时刻 sin/cos 特征，输出为光伏容量因子；使用随机森林回归，"
                  "参数为 n_estimators=240、max_depth=12、min_samples_leaf=8、max_features=0.9、n_jobs=1、random_state=42。"
                  "按日期前 80%/后 20% 做时序切分，训练 2,487 行、测试 670 行。外部测试集 MAE 0.0077、RMSE 0.0156、R² 0.9964；"
                  "同一测试集上的物理基线 MAE 0.0379、RMSE 0.0615。")
    add_body(doc, "把模型迁移到场景 A 的 5832 小时：ML 平均 CF 0.2688，物理平均 CF 0.2336，两者 MAE 0.0352、最大差 0.1069、"
                  "相关系数 0.9997。基准 50/80/20/80 方案下，物理口径年化成本 21,340 万元、LCOE 0.503 元/kWh；"
                  "ML 口径年化成本 19,643 万元、LCOE 0.463 元/kWh。差异来自模型在相同 GHI 下给出更高的 CF，"
                  "不代表目标电站的真实增益。外部数据只有 33 天且位于印度，与江苏沿海项目存在气候、组件和安装角度的域偏移，"
                  "因此 ML 只作为迁移敏感性分析，主结果仍用物理口径。")

    add_h2(doc, "3.8 系统实现")
    add_body(doc, "后端用 FastAPI 实现，主要接口见表 3-4。接口的请求体用 Pydantic 校验：C_w/C_pv ∈ [0,300]，"
                  "C_b ∈ [0,150]，E_b ∈ [0,600]；particles ∈ [4,40]，iters ∈ [3,40]；pv_model ∈ {physical, ml}，"
                  "ML 只允许场景 A。前端用 Vue3 + Vite + ECharts 实现五个页面，生产构建后由 FastAPI 托管 frontend/dist。")
    add_table(doc, ["方法", "路径", "说明"], [
        ["GET", "/api/health", "服务状态、版本、数据包是否存在"],
        ["GET", "/api/scenarios", "场景 A/B 的行数、时间范围、均值"],
        ["POST", "/api/datasets/inspect", "上传 CSV/XLSX，返回体检报告"],
        ["POST", "/api/simulate", "给定容量返回指标；可返回 5832 点时序"],
        ["POST", "/api/optimize", "PSO/GWO 在线优化，保存运行记录"],
        ["GET", "/api/runs", "最近运行记录"],
        ["GET", "/api/reference", "预计算 PSO 参考结果"],
        ["GET", "/api/ml/pv/compare", "场景 A 的 ML/物理逐时对照"],
    ], widths=[1.8, 5.4, 7.0], font_size=8.8, caption="表 3-4  主要后端接口")
    add_body(doc, "数据库使用 SQLite，文件为 data/platform.sqlite3，表 runs 保存运行摘要：id、created_at、scenario、algorithm、"
                  "四个容量、年化成本、LCOE、弃电率、SOC 区间占比、失负荷电量和完整结果 JSON。"
                  "数据库只存摘要，不存 5832 点时序；原始数据和结果文件仍在 data/ 下，便于迁移和复现。"
                  "当前未接入 MySQL，服务器若需要改 MySQL，只需替换 db.py 的数据访问层。")
    add_body(doc, "前端五个页面分别为运行总览、数据管理、机器学习、容量优化和报告输出。运行总览提供场景/方案切换、"
                  "典型日电力平衡、储能 SOC 和月度电量；数据管理支持拖拽上传并返回体检结果；机器学习页展示模型来源、"
                  "测试指标、物理/ML 曲线和误差分布；容量优化页提供 PSO/GWO 参数、在线优化和运行记录；"
                  "报告输出页按章节生成可打印 HTML，并可另存为 PDF。")

    # ---------------------------- 四、实验结果 ----------------------------
    add_page_break(doc)
    add_h1(doc, "四、实验结果")
    add_h2(doc, "4.1 数据体检与描述性分析结果")
    add_body(doc, "03 文件的体检结果为：5832 行、6 列，时间范围 2026-01-01 00:00—2026-08-31 23:00，采样间隔 60 min，"
                  "理论行数 5832，有效行数 5832，覆盖率 100%，重复 0，缺口 0，评分 90，状态 usable_with_warnings。"
                  "唯一提示是 PARTIAL_PERIOD：仅覆盖 243 天，年指标需要标注为期间值或年化估算；购电价的 972 个“离群”是"
                  "三档电价的统计结果，不构成阻断。")
    add_body(doc, "描述性统计显示，负荷均值 48.39 MW、标准差 5.27 MW，峰谷差相对较小；风速均值 6.01 m/s，"
                  "落在 3—11 m/s 的风机爬坡段；温度 14—26 ℃，属于温和区间；GHI 夜间为 0、白天峰值 900 W/m²。"
                  "负荷的平稳性意味着容量优化主要受风光资源与电价驱动，而不是受剧烈负荷波动驱动。")
    add_figure(doc, SHOTS / "data.png", "图 4-1  数据管理页面：上传、体检、列映射与问题清单")
    add_body(doc, "数据管理页面上传后返回行数、时间轴、缺失/重复/物理范围和评分，前端把体检结果与列映射放在同一屏，"
                  "便于在进入仿真前判断数据是否可用。这个页面不是简单的文件预览，而是计算链路的质量门槛。")

    add_h2(doc, "4.2 基准运行结果")
    add_body(doc, "在 50/80/20/80 基准容量下，场景 A 的年化总成本为 21,340.1 万元，LCOE 0.503 元/kWh，弃电率 0，"
                  "绿电占比 53.2%，SOC 30%—80% 占比 52.8%，失负荷为 0。场景 B 的年化成本为 28,069.2 万元，"
                  "LCOE 0.571 元/kWh，弃电率 0，绿电占比 44.9%，SOC 区间占比 43.2%，失负荷 3.08 MWh。"
                  "B 的失负荷来自 05 原始购电峰值 72.3 MW 超过外网 70 MW 限值，是数据口径导致的，不是仿真错误。")
    add_body(doc, "两个场景的成本差异主要来自负荷水平和资源条件不同：B 的负荷峰值更高，且风光出力与负荷的时序匹配不如 A，"
                  "因此需要更多购电。把 A/B 分开计算，可以避免把不同口径的数据混在一起，得到看似“更完整”但不可解释的结论。")
    add_figure(doc, SHOTS / "overview.png", "图 4-2  运行总览页面：指标卡、典型日电力平衡、SOC 与月度电量")

    add_h2(doc, "4.3 容量优化结果")
    add_body(doc, "PSO 在场景 A 的 30 粒子 × 30 代结果为 x = [87.68, 167.70, 0, 0]，即风电 87.68 MW、光伏 167.70 MW、"
                  "储能 0 MW/0 MWh；年化成本 16,802.1 万元，LCOE 0.396 元/kWh，弃电率 3.86%，绿电占比 65.7%，失负荷 0。"
                  "GWO 在同规模下得到 87.61/167.40/0.67/2.94，年化成本 16,815.4 万元，弃电率 3.81%，SOC 区间占比 41.3%。"
                  "两种算法的成本只差约 13 万元，说明经济最优附近比较平坦；PSO 收敛到零储能，GWO 保留了一个很小的储能。")
    add_body(doc, "成本优先时出现零储能，原因有三点：外网 70 MW 可以承担保供；储能不能显著减少长时段弃电；"
                  "储能投资 1200 元/kWh，按 8%、25 年折算后，峰谷价差回收不了投资。这不是代码错误，而是当前数据和成本参数下的经济结果。"
                  "如果要求储能运行在 30%—80%，应把 80/120/40/160 作为友好配置：年化成本 18,759.1 万元，弃电率 0.03%，"
                  "SOC 区间占比 43.8%，比经济最优多约 1,957 万元/年，但弃电率从 3.86% 降到 0.03%。")
    add_table(doc, ["方案", "场景", "容量 W/PV/B/E", "年化成本（万元）", "LCOE（元/kWh）", "弃电率", "绿电占比", "SOC 30—80"], [
        ["基准 50/80/20/80", "A", "50/80/20/80", "21,340.1", "0.503", "0.00%", "53.2%", "52.8%"],
        ["基准 50/80/20/80", "B", "50/80/20/80", "28,069.2", "0.571", "0.00%", "44.9%", "43.2%"],
        ["友好配置", "A", "80/120/40/160", "18,759.1", "—", "0.03%", "—", "43.8%"],
        ["PSO 经济最优", "A", "87.68/167.70/0/0", "16,802.1", "0.396", "3.86%", "65.7%", "—"],
    ], widths=[2.5, 0.95, 3.0, 2.35, 1.9, 1.3, 1.2, 1.2], font_size=8.4, caption="表 4-1  基准与优化方案结果")
    add_body(doc, "表 4-1 中“—”表示该指标不适用或未计算；零储能时 SOC 30%—80% 没有意义，不能按 100% 处理。"
                  "从结果看，经济最优与友好配置不是同一个方案：前者成本低、弃电略高，后者成本高、弃电几乎为零且储能运行在目标区间。"
                  "答辩时建议同时汇报两组结果，并明确“成本优先”与“友好性约束”的区别。")
    add_figure(doc, SHOTS / "optimize.png", "图 4-3  容量优化页面：PSO/GWO 参数、预计算参考与运行记录")

    add_h2(doc, "4.4 机器学习对照结果")
    add_body(doc, "外部测试集上，随机森林的 MAE 为 0.0077、RMSE 为 0.0156、R² 为 0.9964；同测试集物理基线 MAE 为 0.0379、"
                  "RMSE 为 0.0615。迁移到场景 A 后，ML 与物理 CF 的相关系数为 0.9997，MAE 为 0.0352，最大差为 0.1069；"
                  "ML 平均 CF 0.2688，物理平均 CF 0.2336。基准方案的年化成本从 21,340 万元降到 19,643 万元，"
                  "LCOE 从 0.503 降到 0.463 元/kWh，绿电占比从 53.2% 升到 55.8%，弃电率仍为 0。")
    add_table(doc, ["指标", "外部测试集", "场景 A 迁移"], [
        ["MAE", "0.0077", "0.0352（ML vs 物理）"],
        ["RMSE", "0.0156", "—"],
        ["R²", "0.9964", "—"],
        ["平均 CF（ML / 物理）", "—", "0.2688 / 0.2336"],
        ["相关系数", "—", "0.9997"],
        ["最大绝对差", "—", "0.1069"],
    ], widths=[4.8, 4.6, 4.9], caption="表 4-2  机器学习模型与迁移结果")
    add_body(doc, "ML 口径的成本更低，是因为模型在相同 GHI 下给出了更高的 CF，而不是因为项目真的获得了更多光伏电量。"
                  "外部数据只有 33 天，且位于印度，和江苏沿海项目存在气候、组件、安装角度的差异；因此本实验把 ML 定位为"
                  "“公开数据训练 + 本项目推理”的迁移敏感性分析，主结果仍采用物理折算。")
    add_figure(doc, SHOTS / "ml.png", "图 4-4  机器学习页面：模型来源、CF 对照、误差分布与成本对比")

    add_h2(doc, "4.5 系统测试与界面验收")
    add_body(doc, "测试使用 pytest，覆盖数据质量、场景加载、功率平衡、SOC 边界、LCOE、零储能评价、PSO/GWO 收敛、"
                  "API、运行记录和机器学习接口，共 27 个测试全部通过。前端构建产物由 FastAPI 托管，"
                  "访问 http://127.0.0.1:8000/ 可打开运行总览；数据、优化、机器学习、报告页面均可正常返回。")
    add_body(doc, "界面验收重点检查了四类问题：指标卡单位与数值是否一致；典型日功率平衡是否闭合；"
                  "零储能时 SOC 指标是否显示为“—”；优化页运行记录是否把内部场景名转换为“场景 A/B”。"
                  "最终页面去掉了课程口吻、内部文件编号和说教式提示，保留数据来源、口径和适用边界等必要说明。")
    add_figure(doc, SHOTS / "report.png", "图 4-5  报告输出页面：章节选择、HTML 下载与打印/PDF")

    # ---------------------------- 五、实验心得 ----------------------------
    add_page_break(doc)
    add_h1(doc, "五、实验心得")
    add_body(doc, "这次实验让我最直接的体会是：数据分析项目的成败往往不在模型，而在数据口径。最初看到 03 和 05 的负荷、温度、"
                  "风速对不上时，很容易想把两份数据按时间拼成一张“完整表”；但真正逐行核对后会发现，这样做会制造虚假的时间对应关系，"
                  "后续的仿真和优化都会建立在错误前提上。把场景 A/B 分开计算、把 06 只当参考、把 09 标为草稿，虽然结果看起来"
                  "不如“合并成 8760 行”漂亮，但每一个数字都能追溯到来源，这比漂亮更重要。")
    add_body(doc, "第二点体会是仿真和优化必须解耦。优化器不应该自己再写一套功率平衡，否则每次调整调度规则都要改两处，"
                  "结果也无法复现。本实验把 simulate() 作为唯一的评价函数，PSO/GWO 只负责搜索容量，每个候选解都跑完整 5832 小时调度。"
                  "这样做计算量大，但逻辑清晰：优化结果一定能被同一个仿真器复现，答辩时也可以直接展示某个容量方案的逐时曲线。")
    add_body(doc, "第三点体会是“成本优先”会得到反直觉的结论。按照直觉，储能应该能降低弃电、提高绿电占比，所以最优解应该配储能；"
                  "但在外网 70 MW 可以保供、储能投资较高、弃电主要是长时段富余的情况下，模型给出的经济最优是零储能。"
                  "一开始我怀疑是代码写错了，后来通过基准方案、GWO 对照、友好配置复算和手工检查功率平衡，确认这是数据和成本参数下的"
                  "真实结果。这个经历让我意识到，优化结果与直觉不一致时，应该先检查约束、单位和边界，再决定是否接受结论，而不是为了"
                  "“看起来合理”去改模型。")
    add_body(doc, "第四点体会是机器学习不能为了“有”而硬塞。按照要求，我选用公开光伏数据训练容量因子模型，再迁移到本项目数据；"
                  "外部测试 R² 0.9964 很好看，但迁移后 ML 与物理 CF 的差异主要来自域偏移，不能宣称预测了目标电站的真实功率。"
                  "因此我把 ML 放在对照页，明确“外部训练、本项目推理、只作敏感性分析”，主结果仍用物理折算。"
                  "这比把 ML 包装成核心结论更符合实际，也更能回答老师关于“数据从哪来、模型能不能迁移”的追问。")
    add_body(doc, "第五点体会是工程化让分析变得可复现。把数据加载、体检、仿真、优化、机器学习拆成独立模块，用 FastAPI 暴露接口，"
                  "用 Vue3 展示结果，用 pytest 覆盖关键边界，用 SQLite 保存运行摘要，最后用一份报告把数据、公式、参数、结果和界面串起来。"
                  "这套结构让我可以在改一个参数后快速重跑，也让我在答辩时能说清楚“这个数字是从哪个文件、哪个函数、哪条公式来的”。")
    add_body(doc, "当然，实验仍有不足：数据只有 1—8 月，年化是外推；规则调度不是全局最优，LP 下界和 NSGA-II Pareto 前沿还没有接入；"
                  "06 参考结果与 03/05 的口径不一致，只能做对照；外部光伏数据只有 33 天，ML 结果只能做敏感性分析；"
                  "Docker 文件已提供，但本机没有安装 Docker，未做实际构建验证。后续如果继续完善，我会优先补完整年数据和储能约束下的再优化，"
                  "再补 LP 下界与 Pareto 前沿，让“经济最优”和“友好配置”的取舍有更完整的定量依据。")
    add_body(doc, "总的来说，这次实验把课堂上的 Pandas 清洗、描述性统计、时间序列仿真、启发式优化、机器学习和 Web 展示串成了一个"
                  "完整项目。最大的收获不是某一个算法，而是学会了在数据不一致、结果反直觉、时间有限的情况下，如何做取舍、如何验证、"
                  "如何把结论讲清楚。")

    # 文档属性
    doc.core_properties.title = "实验九 源网荷储一体化仿真平台"
    doc.core_properties.subject = "Python 数据分析实验报告"
    doc.core_properties.author = "上海电力大学 人工智能学部"
    doc.core_properties.keywords = "源网荷储, PSO, GWO, 机器学习, Vue3, FastAPI"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"saved: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
