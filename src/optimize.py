"""容量优化：PSO / GWO（单目标最小年化总成本）。

决策变量 x = [C_w, C_pv, C_b, E_b]，单位 MW/MW/MW/MWh。
内层用 `src.simulate.simulate` 做全年/全周期规则调度。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import OUTPUT_DIR
from .loader import ScenarioData, load_scenario_a, load_scenario_b
from .simulate import SimulationParams, simulate

BOUNDS = np.array(
    [
        [0.0, 300.0],   # C_w
        [0.0, 300.0],   # C_pv
        [0.0, 150.0],   # C_b
        [0.0, 600.0],   # E_b
    ],
    dtype=float,
)

DURATION_MIN = 2.0
DURATION_MAX = 6.0
PENALTY_ENS = 1e7       # 元/MWh
PENALTY_DURATION = 1e6  # 元/(MWh 违约)


@dataclass
class Evaluation:
    x: np.ndarray
    fitness: float
    annual_cost: float
    curtail_rate: float
    soc_in_band_ratio: float
    ens_mwh: float
    reliability: float
    lcoe: float
    duration_violation: float
    metrics: dict


@dataclass
class OptimizationResult:
    algorithm: str
    scenario: str
    best_x: list[float]
    best_fitness: float
    best_metrics: dict
    history: list[float]
    runtime_s: float
    n_evals: int
    bounds: list[list[float]]
    best_metrics_series: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("best_metrics_series", None)
        return data


def make_params(x: np.ndarray) -> SimulationParams:
    cw, cpv, cb, eb = (float(v) for v in x)
    return SimulationParams(C_w=cw, C_pv=cpv, C_b=cb, E_b=eb)


def duration_violation(params: SimulationParams) -> float:
    if params.C_b <= 0:
        return 0.0 if params.E_b <= 0 else params.E_b
    duration = params.E_b / params.C_b
    return max(0.0, DURATION_MIN - duration) + max(0.0, duration - DURATION_MAX)


def evaluate(x: np.ndarray, scenario: ScenarioData) -> Evaluation:
    x = np.asarray(x, dtype=float)
    params = make_params(x)
    result = simulate(scenario, params)
    dv = duration_violation(params)
    fitness = (
        result.annual_cost
        + PENALTY_ENS * max(0.0, result.ens_mwh)
        + PENALTY_DURATION * dv
    )
    return Evaluation(
        x=x,
        fitness=float(fitness),
        annual_cost=float(result.annual_cost),
        curtail_rate=float(result.curtail_rate),
        soc_in_band_ratio=float(result.soc_in_band_ratio),
        ens_mwh=float(result.ens_mwh),
        reliability=float(result.reliability),
        lcoe=float(result.lcoe),
        duration_violation=float(dv),
        metrics=result.metrics(),
    )


def _clip(x: np.ndarray, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:
    return np.minimum(np.maximum(x, lb), ub)


def repair(x: np.ndarray) -> np.ndarray:
    """把候选解投影到可行域：容量边界 + 储能 2–6 小时。"""
    lb, ub = BOUNDS[:, 0], BOUNDS[:, 1]
    x = _clip(np.asarray(x, dtype=float), lb, ub).copy()
    cw, cpv, cb, eb = x
    if cb <= 0.0 and eb <= 0.0:
        return x
    if cb <= 0.0:
        cb = min(ub[2], max(lb[2], eb / 4.0))
    if eb <= 0.0:
        eb = 2.0 * cb
    eb = min(ub[3], max(lb[3], 2.0 * cb, min(eb, 6.0 * cb)))
    x[2], x[3] = cb, eb
    return x


def pso(
    scenario: ScenarioData,
    n_particles: int = 30,
    n_iters: int = 100,
    seed: int = 42,
    verbose: bool = True,
) -> OptimizationResult:
    rng = np.random.default_rng(seed)
    lb, ub = BOUNDS[:, 0], BOUNDS[:, 1]
    dim = len(lb)

    X = np.array([repair(lb + rng.random(dim) * (ub - lb)) for _ in range(n_particles)])
    V = np.zeros_like(X)
    pbest = X.copy()
    pbest_f = np.full(n_particles, np.inf)
    gbest = X[0].copy()
    gbest_f = np.inf
    history: list[float] = []
    n_evals = 0
    t0 = time.perf_counter()

    for it in range(n_iters):
        for i in range(n_particles):
            ev = evaluate(X[i], scenario)
            n_evals += 1
            if ev.fitness < pbest_f[i]:
                pbest_f[i] = ev.fitness
                pbest[i] = X[i].copy()
            if ev.fitness < gbest_f:
                gbest_f = ev.fitness
                gbest = X[i].copy()

        history.append(float(gbest_f))
        if verbose:
            print(
                f"[PSO] iter {it + 1}/{n_iters} "
                f"best={gbest_f / 1e4:.1f}万元 "
                f"x=[{gbest[0]:.1f},{gbest[1]:.1f},{gbest[2]:.1f},{gbest[3]:.1f}]"
            )

        w = 0.9 - 0.5 * it / max(1, n_iters - 1)
        c1 = c2 = 1.5
        r1 = rng.random((n_particles, dim))
        r2 = rng.random((n_particles, dim))
        V = w * V + c1 * r1 * (pbest - X) + c2 * r2 * (gbest - X)
        X = np.array([repair(row) for row in _clip(X + V, lb, ub)])

    gbest = repair(gbest)
    best_params = make_params(gbest)
    best_result = simulate(scenario, best_params, keep_series=True)
    runtime = time.perf_counter() - t0
    return OptimizationResult(
        algorithm="PSO",
        scenario=scenario.name,
        best_x=[float(v) for v in gbest],
        best_fitness=float(gbest_f),
        best_metrics=best_result.metrics(),
        best_metrics_series=best_result.series,  # type: ignore[call-arg]
        history=history,
        runtime_s=float(runtime),
        n_evals=n_evals,
        bounds=BOUNDS.tolist(),
    )


def gwo(
    scenario: ScenarioData,
    n_wolves: int = 30,
    n_iters: int = 100,
    seed: int = 42,
    verbose: bool = True,
) -> OptimizationResult:
    rng = np.random.default_rng(seed)
    lb, ub = BOUNDS[:, 0], BOUNDS[:, 1]
    dim = len(lb)

    X = np.array([repair(lb + rng.random(dim) * (ub - lb)) for _ in range(n_wolves)])
    alpha = X[0].copy()
    beta = X[0].copy()
    delta = X[0].copy()
    alpha_f = beta_f = delta_f = np.inf
    history: list[float] = []
    n_evals = 0
    t0 = time.perf_counter()

    for it in range(n_iters):
        for i in range(n_wolves):
            ev = evaluate(X[i], scenario)
            n_evals += 1
            if ev.fitness < alpha_f:
                delta_f, delta = beta_f, beta.copy()
                beta_f, beta = alpha_f, alpha.copy()
                alpha_f, alpha = ev.fitness, X[i].copy()
            elif ev.fitness < beta_f:
                delta_f, delta = beta_f, beta.copy()
                beta_f, beta = ev.fitness, X[i].copy()
            elif ev.fitness < delta_f:
                delta_f, delta = ev.fitness, X[i].copy()

        history.append(float(alpha_f))
        if verbose:
            print(
                f"[GWO] iter {it + 1}/{n_iters} "
                f"best={alpha_f / 1e4:.1f}万元 "
                f"x=[{alpha[0]:.1f},{alpha[1]:.1f},{alpha[2]:.1f},{alpha[3]:.1f}]"
            )

        a = 2.0 - 2.0 * it / max(1, n_iters - 1)
        for i in range(n_wolves):
            X1 = _gwo_move(alpha, X[i], a, rng)
            X2 = _gwo_move(beta, X[i], a, rng)
            X3 = _gwo_move(delta, X[i], a, rng)
            X[i] = repair(_clip((X1 + X2 + X3) / 3.0, lb, ub))

    alpha = repair(alpha)
    best_params = make_params(alpha)
    best_result = simulate(scenario, best_params, keep_series=True)
    runtime = time.perf_counter() - t0
    return OptimizationResult(
        algorithm="GWO",
        scenario=scenario.name,
        best_x=[float(v) for v in alpha],
        best_fitness=float(alpha_f),
        best_metrics=best_result.metrics(),
        best_metrics_series=best_result.series,  # type: ignore[call-arg]
        history=history,
        runtime_s=float(runtime),
        n_evals=n_evals,
        bounds=BOUNDS.tolist(),
    )


def _gwo_move(leader: np.ndarray, wolf: np.ndarray, a: float, rng: np.random.Generator) -> np.ndarray:
    r1 = rng.random(len(wolf))
    r2 = rng.random(len(wolf))
    A = 2.0 * a * r1 - a
    C = 2.0 * r2
    D = np.abs(C * leader - wolf)
    return leader - A * D


def save_result(result: OptimizationResult, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"opt_{result.scenario}_{result.algorithm.lower()}.json"
    data = result.to_dict()
    data["best_series"] = result.best_metrics_series  # type: ignore[attr-defined]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="PSO/GWO 容量优化")
    parser.add_argument("--scenario", choices=["A", "B"], default="A")
    parser.add_argument("--algo", choices=["pso", "gwo"], default="pso")
    parser.add_argument("--particles", type=int, default=30)
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    scenario = load_scenario_a() if args.scenario == "A" else load_scenario_b()
    verbose = not args.quiet
    if args.algo == "pso":
        result = pso(scenario, args.particles, args.iters, args.seed, verbose=verbose)
    else:
        result = gwo(scenario, args.particles, args.iters, args.seed, verbose=verbose)

    path = save_result(result)
    print("\n=== best ===")
    print("scenario", result.scenario, result.algorithm)
    print("x", [round(v, 2) for v in result.best_x])
    print("fitness", round(result.best_fitness / 1e4, 1), "万元/年")
    print("annual_cost", round(result.best_metrics["annual_cost"] / 1e4, 1), "万元/年")
    print("curtail", round(result.best_metrics["curtail_rate"], 4))
    print("soc_in_band", round(result.best_metrics["soc_in_band_ratio"], 3))
    print("ens", round(result.best_metrics["ens_mwh"], 3), "MWh")
    print("saved", path)


if __name__ == "__main__":
    main()
