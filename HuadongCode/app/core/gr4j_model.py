"""Unified GR4J wrapper and spotpy calibration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import spotpy

from app.core.calibrated_parameters import load_calibrated_parameters
from app.core.gr4j import gr4j
from app.core.xaj_model import nse


_DEFAULT_ORIGINAL_PARAMS = np.array([300.0, 0.0, 80.0, 24.0], dtype=float)


@dataclass
class GR4JRunResult:
    streamflow: list[float]
    evap: list[float]


class GR4JModelRunner:
    """Thin forecast/calibration wrapper around app.core.gr4j.gr4j."""

    def __init__(
        self,
        basin_area_km2: float = 3300.0,
        warmup_length: int = 0,
    ) -> None:
        self.basin_area_km2 = basin_area_km2
        self.warmup_length = warmup_length

    @property
    def flow_factor(self) -> float:
        return self.basin_area_km2 / 3.6

    def _build_input(
        self, rainfall: Sequence[float], pet: Sequence[float]
    ) -> np.ndarray:
        return np.stack(
            [
                np.asarray(rainfall, dtype=float),
                np.asarray(pet, dtype=float),
            ],
            axis=1,
        )[:, np.newaxis, :]

    def simulate(
        self,
        rainfall: Sequence[float],
        pet: Sequence[float],
        params: Sequence[float] | None = None,
        warmup_length: int | None = None,
        normalized_params: bool | None = None,
    ) -> GR4JRunResult:
        if params is None:
            try:
                params_arr, normalized_flag = load_calibrated_parameters("gr4j")
            except FileNotFoundError:
                params_arr = _DEFAULT_ORIGINAL_PARAMS.copy()
                normalized_flag = False
        else:
            params_arr = np.asarray(params, dtype=float)
            normalized_flag = False if normalized_params is None else normalized_params

        q_sim, evap = gr4j(
            self._build_input(rainfall, pet),
            params_arr.reshape(1, -1),
            warmup_length=self.warmup_length if warmup_length is None else warmup_length,
            normalized_params=normalized_flag,
        )
        q_series = np.asarray(q_sim, dtype=float).reshape(-1) * self.flow_factor
        e_series = np.asarray(evap, dtype=float).reshape(-1)
        return GR4JRunResult(streamflow=q_series.tolist(), evap=e_series.tolist())

    def predict(
        self,
        rainfall: Sequence[float],
        pet: Sequence[float],
        params: Sequence[float] | None = None,
        warmup_length: int | None = None,
        normalized_params: bool | None = None,
    ) -> list[float]:
        return self.simulate(
            rainfall=rainfall,
            pet=pet,
            params=params,
            warmup_length=warmup_length,
            normalized_params=normalized_params,
        ).streamflow


class GR4JSpotpyAdapter:
    """spotpy adapter aligned with old_code/GR4J style."""

    def __init__(
        self,
        runner: GR4JModelRunner,
        rainfall: Sequence[float],
        pet: Sequence[float],
        observations: Sequence[float],
        timestamps: Sequence,
        train_period: tuple[str, str],
        warmup_length: int = 720,
    ) -> None:
        self.runner = runner
        self.rainfall = np.asarray(rainfall, dtype=float)
        self.pet = np.asarray(pet, dtype=float)
        self.observations = np.asarray(observations, dtype=float)
        self.warmup_length = warmup_length
        self.eval_obs = self.observations[warmup_length:]
        self.eval_time = np.asarray(list(timestamps))[warmup_length:]

        start = np.datetime64(train_period[0])
        end = np.datetime64(train_period[1])
        train_time = self.eval_time.astype("datetime64[ns]")
        self.train_mask = (train_time >= start) & (train_time <= end)
        if not np.any(self.train_mask):
            raise ValueError("train_period does not overlap evaluation series")

        self.param_names = ["x1", "x2", "x3", "x4"]
        self.params = [
            spotpy.parameter.Uniform("x1", 50.0, 2000.0),
            spotpy.parameter.Uniform("x2", -0.2, 0.2),
            spotpy.parameter.Uniform("x3", 20.0, 500.0),
            spotpy.parameter.Uniform("x4", 12.0, 96.0),
        ]

    def parameters(self):
        return spotpy.parameter.generate(self.params)

    def simulation(self, vector):
        return np.asarray(
            self.runner.predict(
                rainfall=self.rainfall,
                pet=self.pet,
                params=np.asarray(vector, dtype=float),
                warmup_length=self.warmup_length,
                normalized_params=False,
            ),
            dtype=float,
        )

    def evaluation(self):
        return self.eval_obs

    def objectivefunction(self, simulation, evaluation):
        sim_train = np.asarray(simulation, dtype=float)[self.train_mask]
        obs_train = np.asarray(evaluation, dtype=float)[self.train_mask]
        return -nse(obs_train, sim_train)


def calibrate_gr4j_with_spotpy(
    rainfall: Sequence[float],
    pet: Sequence[float],
    observations: Sequence[float],
    timestamps: Sequence,
    train_period: tuple[str, str],
    basin_area_km2: float = 3300.0,
    repetitions: int = 3000,
    ngs: int = 5,
    warmup_length: int = 720,
) -> dict:
    runner = GR4JModelRunner(basin_area_km2=basin_area_km2, warmup_length=warmup_length)
    adapter = GR4JSpotpyAdapter(
        runner=runner,
        rainfall=rainfall,
        pet=pet,
        observations=observations,
        timestamps=timestamps,
        train_period=train_period,
        warmup_length=warmup_length,
    )
    sampler = spotpy.algorithms.sceua(
        adapter,
        dbname="gr4j_spotpy_results",
        dbformat="ram",
        save_sim=False,
    )
    sampler.sample(repetitions=repetitions, ngs=ngs, kstop=max(10, ngs))
    results = sampler.getdata()
    best_row = results[np.argmin(results["like1"])]
    best_params = np.array(
        [float(best_row[f"par{name}"]) for name in adapter.param_names], dtype=float
    )
    train_nse = float(-best_row["like1"])
    return {
        "runner": runner,
        "best_params": best_params,
        "train_nse": train_nse,
        "param_names": adapter.param_names,
        "repetitions": repetitions,
    }
