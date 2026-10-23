"""容量配置与全年/全周期运行仿真。

规则调度：风光优先供负荷；富余充储→上网→弃电；缺额放储→购电→失负荷。
SOC 硬安全边界 10%–95%，软目标 30%–80%（越界罚）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from .config import COST, DEVICE
from .loader import ScenarioData


@dataclass
class SimulationParams:
    C_w: float
    C_pv: float
    C_b: float
    E_b: float
    grid_in_mw: float = 70.0
    grid_out_mw: float = 70.0
    eta: float = 0.92
    soc_min: float = 0.10
    soc_max: float = 0.95
    soc_soft_min: float = 0.30
    soc_soft_max: float = 0.80
    soc0: float = 0.55
    curtail_penalty: float = 0.05       # 元/kWh
    soc_penalty: float = 0.10            # 元/kWh 越界电量
    ens_penalty: float = 100.0           # 元/kWh 失负荷
    end_soc_penalty: float = 50.0        # 元/kWh 末期 SOC 偏差
    carbon_factor: float = 0.5703        # tCO2/MWh
    carbon_price: float = COST["carbon_price_yuan_per_t"]
    discount_rate: float = COST["discount_rate"]
    years: int = 25
    om_rate: float = 0.015
    grid_charge_valley: bool = True
    valley_price_threshold: float = 0.40
    grid_charge_target_soc: float = 0.80

    def validate(self) -> None:
        if min(self.C_w, self.C_pv, self.C_b, self.E_b) < 0:
            raise ValueError("容量不能为负")
        if not (0.0 <= self.soc_min < self.soc_soft_min < self.soc_soft_max < self.soc_max <= 1.0):
            raise ValueError("SOC 边界顺序应为 0 ≤ min < soft_min < soft_max < max ≤ 1")
        if self.soc0 < self.soc_min or self.soc0 > self.soc_max:
            raise ValueError("初始 SOC 必须在硬边界内")


@dataclass
class SimulationResult:
    annual_cost: float
    period_cost: float
    capex: float
    annual_capex: float
    om: float
    grid_cost: float
    export_revenue: float
    carbon_cost: float
    curtail_cost: float
    soc_cost: float
    ens_cost: float
    end_soc_cost: float
    lcoe: float
    curtail_mwh: float
    curtail_rate: float
    re_available_mwh: float
    re_used_mwh: float
    green_ratio: float
    reliability: float
    soc_in_band_ratio: float
    soc_out_mwh: float
    ens_mwh: float
    grid_buy_mwh: float
    grid_sell_mwh: float
    load_mwh: float
    end_soc: float
    annual_factor: float
    series: dict[str, Any] | None = None

    def metrics(self) -> dict[str, float]:
        data = asdict(self)
        data.pop("series", None)
        return {k: float(v) for k, v in data.items()}


def crf(rate: float, years: int) -> float:
    if rate <= 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def simulate(
    scenario: ScenarioData,
    params: SimulationParams,
    keep_series: bool = False,
) -> SimulationResult:
    params.validate()
    n = scenario.hours
    if n == 0:
        raise ValueError("场景没有数据")

    wcf = np.asarray(scenario.wind_cf, dtype=float)
    pcf = np.asarray(scenario.pv_cf, dtype=float)
    load = np.asarray(scenario.load_mw, dtype=float)
    price = np.asarray(scenario.price_buy, dtype=float)

    cw, cpv = params.C_w, params.C_pv
    cb, eb = params.C_b, params.E_b
    eta = params.eta
    soc = float(np.clip(params.soc0, params.soc_min, params.soc_max))

    soc_arr = np.empty(n)
    ch_arr = np.empty(n)
    dis_arr = np.empty(n)
    gin_arr = np.empty(n)
    gout_arr = np.empty(n)
    cur_arr = np.empty(n)
    ens_arr = np.empty(n)
    wind_used_arr = np.empty(n)
    pv_used_arr = np.empty(n)

    soc_out_energy = 0.0
    grid_cost = 0.0
    export_revenue = 0.0

    for i in range(n):
        avail_w = cw * wcf[i]
        avail_p = cpv * pcf[i]
        re = avail_w + avail_p
        net = re - load[i]
        ch = dis = gin = gout = cur = ens = 0.0

        if net >= 0.0:
            if eb > 0.0 and cb > 0.0:
                max_ch = min(cb, max(0.0, (params.soc_max - soc) * eb / eta))
                ch = min(net, max_ch)
                soc += ch * eta / eb
            rest = net - ch
            gout = min(rest, params.grid_out_mw)
            cur = max(0.0, rest - gout)
            export_revenue += scenario.price_sell * gout * 1000.0
        else:
            deficit = -net
            valley = params.grid_charge_valley and price[i] <= params.valley_price_threshold
            if valley and eb > 0.0 and cb > 0.0 and soc < params.grid_charge_target_soc:
                # 谷段：电网优先供负荷，剩余容量给储能充电，留给峰段放电
                gin = min(deficit, params.grid_in_mw)
                rest = deficit - gin
                if rest > 0.0:
                    max_dis = min(cb, max(0.0, (soc - params.soc_min) * eb * eta))
                    dis = min(rest, max_dis)
                    rest -= dis
                    soc -= dis / (eta * eb)
                ens = max(0.0, rest)
                headroom = max(0.0, params.grid_in_mw - gin)
                if headroom > 0.0:
                    max_ch = min(cb, headroom, max(0.0, (params.soc_max - soc) * eb / eta))
                    target = max(0.0, (params.grid_charge_target_soc - soc) * eb / eta)
                    ch = min(max_ch, target)
                    soc += ch * eta / eb
                    gin += ch
            else:
                if eb > 0.0 and cb > 0.0:
                    max_dis = min(cb, max(0.0, (soc - params.soc_min) * eb * eta))
                    dis = min(deficit, max_dis)
                    soc -= dis / (eta * eb)
                rest = deficit - dis
                gin = min(rest, params.grid_in_mw)
                ens = max(0.0, rest - gin)

        grid_cost += price[i] * gin * 1000.0

        if soc < params.soc_min:
            soc = params.soc_min
        elif soc > params.soc_max:
            soc = params.soc_max

        excursion = (
            max(0.0, params.soc_soft_min - soc) + max(0.0, soc - params.soc_soft_max)
        ) * eb
        soc_out_energy += excursion

        # 按可用出力比例分摊弃电，便于展示
        if cur > 0.0 and re > 0.0:
            wind_used = avail_w * (1.0 - cur / re)
            pv_used = avail_p * (1.0 - cur / re)
        else:
            wind_used, pv_used = avail_w, avail_p

        soc_arr[i] = soc
        ch_arr[i] = ch
        dis_arr[i] = dis
        gin_arr[i] = gin
        gout_arr[i] = gout
        cur_arr[i] = cur
        ens_arr[i] = ens
        wind_used_arr[i] = wind_used
        pv_used_arr[i] = pv_used

    # 能量（MWh，Δt=1h）
    load_mwh = float(load.sum())
    grid_buy_mwh = float(gin_arr.sum())
    grid_sell_mwh = float(gout_arr.sum())
    curtail_mwh = float(cur_arr.sum())
    ens_mwh = float(ens_arr.sum())
    re_available_mwh = float((cw * wcf + cpv * pcf).sum())
    re_used_mwh = re_available_mwh - curtail_mwh

    # 投资与年化
    capex = (
        COST["wind_capex_yuan_per_kw"] * 1000.0 * cw
        + COST["pv_capex_yuan_per_kw"] * 1000.0 * cpv
        + COST["battery_capex_yuan_per_kwh"] * 1000.0 * eb
    )
    annual_capex = capex * crf(params.discount_rate, params.years)
    om = capex * params.om_rate

    carbon_cost = grid_buy_mwh * params.carbon_factor * params.carbon_price
    curtail_cost = curtail_mwh * params.curtail_penalty * 1000.0
    soc_cost = soc_out_energy * params.soc_penalty * 1000.0
    ens_cost = ens_mwh * params.ens_penalty * 1000.0
    end_soc_cost = abs(soc - params.soc0) * eb * params.end_soc_penalty * 1000.0

    variable_period = (
        grid_cost
        - export_revenue
        + carbon_cost
        + curtail_cost
        + soc_cost
        + ens_cost
        + end_soc_cost
    )
    annual_factor = 8760.0 / n
    annual_cost = annual_capex + om + variable_period * annual_factor
    period_cost = (annual_capex + om) * (n / 8760.0) + variable_period
    lcoe = annual_cost / (load_mwh * annual_factor) / 1000.0 if load_mwh > 0 else float("inf")

    curtail_rate = curtail_mwh / re_available_mwh if re_available_mwh > 0 else 0.0
    green_ratio = 1.0 - grid_buy_mwh / load_mwh if load_mwh > 0 else 0.0
    reliability = 1.0 - ens_mwh / load_mwh if load_mwh > 0 else 0.0
    if eb > 0.0:
        in_band = np.mean((soc_arr >= params.soc_soft_min) & (soc_arr <= params.soc_soft_max))
    else:
        # 没有储能时不存在 SOC 区间合规，不能按“100% 在区间内”计
        in_band = 0.0

    series = None
    if keep_series:
        series = {
            "timestamps": scenario.timestamps.astype(str).tolist(),
            "soc": soc_arr.tolist(),
            "battery_charge": ch_arr.tolist(),
            "battery_discharge": dis_arr.tolist(),
            "grid_buy": gin_arr.tolist(),
            "grid_sell": gout_arr.tolist(),
            "curtail": cur_arr.tolist(),
            "ens": ens_arr.tolist(),
            "wind_used": wind_used_arr.tolist(),
            "pv_used": pv_used_arr.tolist(),
            "load": load.tolist(),
        }

    return SimulationResult(
        annual_cost=float(annual_cost),
        period_cost=float(period_cost),
        capex=float(capex),
        annual_capex=float(annual_capex),
        om=float(om),
        grid_cost=float(grid_cost),
        export_revenue=float(export_revenue),
        carbon_cost=float(carbon_cost),
        curtail_cost=float(curtail_cost),
        soc_cost=float(soc_cost),
        ens_cost=float(ens_cost),
        end_soc_cost=float(end_soc_cost),
        lcoe=float(lcoe),
        curtail_mwh=curtail_mwh,
        curtail_rate=float(curtail_rate),
        re_available_mwh=re_available_mwh,
        re_used_mwh=re_used_mwh,
        green_ratio=float(green_ratio),
        reliability=float(reliability),
        soc_in_band_ratio=float(in_band),
        soc_out_mwh=float(soc_out_energy),
        ens_mwh=ens_mwh,
        grid_buy_mwh=grid_buy_mwh,
        grid_sell_mwh=grid_sell_mwh,
        load_mwh=load_mwh,
        end_soc=float(soc),
        annual_factor=float(annual_factor),
        series=series,
    )
