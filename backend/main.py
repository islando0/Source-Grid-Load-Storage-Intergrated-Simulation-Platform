from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import BASE_DIR, OUTPUT_DIR, PROJECT, SOURCE_PACKAGE
from src.db import db_path, list_runs, save_run
from src.loader import load_scenario_a, load_scenario_b
from src.ml.pv import apply_to_scenario, compare_on_scenario, model_info
from src.optimize import gwo, pso
from src.quality import inspect_bytes
from src.simulate import SimulationParams, simulate

VERSION = "0.1.0"

app = FastAPI(
    title="友好型源网荷储一体化规划配置仿真平台",
    version=VERSION,
    description="数据分析、容量优化、运行仿真与可视化平台",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "snl-platform",
        "version": VERSION,
        "project": PROJECT["name"],
        "data_package_found": SOURCE_PACKAGE.exists(),
    }


@app.get("/api/meta")
def meta() -> dict:
    return {
        "project": PROJECT,
        "data_package": str(SOURCE_PACKAGE),
    }


@app.post("/api/datasets/inspect")
async def inspect_dataset(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    try:
        return inspect_bytes(file.filename or "upload.csv", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class SimulateRequest(BaseModel):
    scenario: Literal["A", "B"] = "A"
    C_w: float = Field(default=50.0, ge=0.0, le=300.0)
    C_pv: float = Field(default=80.0, ge=0.0, le=300.0)
    C_b: float = Field(default=20.0, ge=0.0, le=150.0)
    E_b: float = Field(default=80.0, ge=0.0, le=600.0)
    pv_model: Literal["physical", "ml"] = "physical"
    keep_series: bool = False


@app.get("/api/scenarios")
def scenarios() -> dict:
    items = []
    for sid, loader in (("A", load_scenario_a), ("B", load_scenario_b)):
        s = loader()
        items.append({"id": sid, "name": s.name, "hours": s.hours, "meta": s.meta})
    return {"scenarios": items}


@app.get("/api/ml/pv")
def ml_pv_info() -> dict:
    """外部光伏模型的信息与测试集指标。"""
    return model_info()


@app.get("/api/ml/pv/compare")
def ml_pv_compare() -> dict:
    """把外部模型迁移到 03 场景，与物理折算逐时对照。"""
    try:
        return compare_on_scenario(load_scenario_a())
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/simulate")
def run_simulate(req: SimulateRequest) -> dict:
    scenario = load_scenario_a() if req.scenario == "A" else load_scenario_b()
    if req.pv_model == "ml":
        if req.scenario != "A":
            raise HTTPException(status_code=400, detail="外部光伏模型只适用于含 GHI 的场景 A")
        try:
            scenario = apply_to_scenario(scenario)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = SimulationParams(C_w=req.C_w, C_pv=req.C_pv, C_b=req.C_b, E_b=req.E_b)
    try:
        result = simulate(scenario, params, keep_series=req.keep_series)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = {
        "scenario": scenario.name,
        "params": {
            "C_w": req.C_w,
            "C_pv": req.C_pv,
            "C_b": req.C_b,
            "E_b": req.E_b,
        },
        "pv_model": req.pv_model,
        "metrics": result.metrics(),
    }
    if req.keep_series:
        payload["series"] = result.series
    return payload


class OptimizeRequest(BaseModel):
    scenario: Literal["A", "B"] = "A"
    algorithm: Literal["pso", "gwo"] = "pso"
    particles: int = Field(default=12, ge=4, le=40)
    iters: int = Field(default=8, ge=3, le=40)
    seed: int = Field(default=42, ge=0, le=9999)


@app.post("/api/optimize")
def run_optimize(req: OptimizeRequest) -> dict:
    scenario = load_scenario_a() if req.scenario == "A" else load_scenario_b()
    try:
        if req.algorithm == "pso":
            result = pso(scenario, req.particles, req.iters, req.seed, verbose=False)
        else:
            result = gwo(scenario, req.particles, req.iters, req.seed, verbose=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = result.to_dict()
    run_id = save_run(
        scenario=scenario.name,
        algorithm=result.algorithm,
        x=result.best_x,
        metrics=result.best_metrics,
        payload=payload,
    )
    payload["run_id"] = run_id
    return payload


@app.get("/api/runs")
def runs(limit: int = 20) -> dict:
    return {"runs": list_runs(limit), "db": str(db_path())}


@app.get("/api/reference")
def reference() -> dict:
    """预计算参考结果（用于前端对照，不参与在线优化）。"""
    import json

    path = OUTPUT_DIR / "opt_A_03_planning_pso.json"
    if not path.exists():
        return {"available": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "scenario": data.get("scenario"),
        "best_x": data.get("best_x"),
        "best_metrics": data.get("best_metrics"),
        "runtime_s": data.get("runtime_s"),
        "n_evals": data.get("n_evals"),
        "algorithm": data.get("algorithm"),
    }


# 前端构建完成后由同一个进程托管；开发阶段用 Vite 代理。
_dist = BASE_DIR / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
