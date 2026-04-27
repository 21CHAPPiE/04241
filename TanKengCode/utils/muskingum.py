from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class MuskingumParams:
    K: float = 5.0
    x: float = 0.25
    dt: float = 1.0

    @property
    def C0(self) -> float:
        denom = self.K * (1 - self.x) + 0.5 * self.dt
        return (0.5 * self.dt - self.K * self.x) / denom

    @property
    def C1(self) -> float:
        denom = self.K * (1 - self.x) + 0.5 * self.dt
        return (0.5 * self.dt + self.K * self.x) / denom

    @property
    def C2(self) -> float:
        denom = self.K * (1 - self.x) + 0.5 * self.dt
        return (self.K * (1 - self.x) - 0.5 * self.dt) / denom

    def validate(self) -> None:
        if not 0.0 <= self.x <= 0.5:
            raise ValueError(f"x must be in [0, 0.5], got {self.x}")
        if self.K <= 0:
            raise ValueError(f"K must be positive, got {self.K}")
        if self.dt <= 0:
            raise ValueError(f"dt must be positive, got {self.dt}")


@dataclass
class MuskingumRouter:
    params: MuskingumParams = field(default_factory=MuskingumParams)
    _last_inflow: float = field(default=0.0, init=False, repr=False)
    _last_outflow: float = field(default=0.0, init=False, repr=False)

    def reset(self, initial_flow: float = 0.0) -> None:
        self._last_inflow = initial_flow
        self._last_outflow = initial_flow

    def route_step(self, current_inflow: float) -> float:
        p = self.params
        outflow = p.C0 * current_inflow + p.C1 * self._last_inflow + p.C2 * self._last_outflow
        outflow = max(0.0, outflow)
        self._last_inflow = current_inflow
        self._last_outflow = outflow
        return outflow

    def route_series(self, inflow_series: Sequence[float], initial_flow: float | None = None) -> list[float]:
        if initial_flow is None:
            initial_flow = float(inflow_series[0]) if inflow_series else 0.0
        self.reset(initial_flow)
        return [self.route_step(float(value)) for value in inflow_series]


def compute_hecheng_flow(
    tankan_outflow_series: Sequence[float],
    interval_flow_series: Sequence[float] | None = None,
    muskingum_params: MuskingumParams | None = None,
    initial_flow: float | None = None,
) -> dict[str, list[float]]:
    params = muskingum_params or MuskingumParams()
    params.validate()

    router = MuskingumRouter(params=params)
    routed = router.route_series(tankan_outflow_series, initial_flow)
    count = len(tankan_outflow_series)

    if interval_flow_series is None:
        interval = [0.0] * count
    else:
        interval = [float(value) for value in interval_flow_series[:count]]
        if len(interval) < count and interval:
            interval.extend([interval[-1]] * (count - len(interval)))
        elif len(interval) < count:
            interval = [0.0] * count

    hecheng_total = [left + right for left, right in zip(routed, interval)]
    return {
        "tankan_routed": routed,
        "interval_flow": interval,
        "hecheng_total": hecheng_total,
    }


def check_downstream_safety(
    hecheng_flow_series: Sequence[float],
    safe_flow: float = 14000.0,
) -> dict[str, object]:
    flows = list(hecheng_flow_series)
    max_flow = max(flows) if flows else 0.0
    exceedances = [
        {"step": index, "flow": round(flow, 1), "excess": round(flow - safe_flow, 1)}
        for index, flow in enumerate(flows)
        if flow > safe_flow
    ]
    return {
        "safe": len(exceedances) == 0,
        "max_flow": round(max_flow, 1),
        "safe_flow": safe_flow,
        "exceedance_count": len(exceedances),
        "exceedances": exceedances,
        "max_exceedance": round(max((item["excess"] for item in exceedances), default=0.0), 1),
    }
