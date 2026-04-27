"""Unified XAJ wrapper and spotpy calibration helpers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import spotpy

from app.core.calibrated_parameters import load_calibrated_parameters
from app.core.model_config import MODEL_PARAM_DICT
from app.core.xaj import xaj


def _param_ranges() -> OrderedDict[str, list[float]]:
    return MODEL_PARAM_DICT["xaj"]["param_range"]


def _default_params() -> np.ndarray:
    return np.full(len(_param_ranges()), 0.5, dtype=float)


@dataclass
class XAJRunResult:
    streamflow: list[float]
    evap: list[float]


class XAJModelRunner:
    """Thin forecast/calibration wrapper around app.core.xaj.xaj."""

    def __init__(
        self,
        basin_area_km2: float = 3300.0,
        time_interval_hours: int = 1,
        warmup_length: int = 0,
    ) -> None:
        self.basin_area_km2 = basin_area_km2
        self.time_interval_hours = time_interval_hours
        self.warmup_length = warmup_length

    @property
    def flow_factor(self) -> float:
        return self.basin_area_km2 / 3.6

    @staticmethod
    def default_pet(rainfall: Sequence[float], temp: Sequence[float] | None = None) -> list[float]:
        if temp is None:
            temp = [20.0] * len(rainfall)
        return [max(0.408 * float(t), 0.0) for t in temp]

    def _build_input(self, rainfall: Sequence[float], pet: Sequence[float]) -> np.ndarray:
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
        pet: Sequence[float] | None = None,
        params: Sequence[float] | None = None,
        warmup_length: int | None = None,
        initial_states: dict[str, float] | None = None,
    ) -> XAJRunResult:
        rainfall_arr = np.asarray(rainfall, dtype=float)
        if pet is None:
            pet_arr = np.asarray(self.default_pet(rainfall_arr), dtype=float)
        else:
            pet_arr = np.asarray(pet, dtype=float)

        if params is None:
            try:
                params_arr, normalized_params = load_calibrated_parameters("xaj")
            except FileNotFoundError:
                params_arr = _default_params()
                normalized_params = True
        else:
            params_arr = np.asarray(params, dtype=float)
            normalized_params = True

        q_sim, es = xaj(
            self._build_input(rainfall_arr, pet_arr),
            params_arr.reshape(1, -1),
            warmup_length=self.warmup_length if warmup_length is None else warmup_length,
            normalized_params=normalized_params,
            name="xaj",
            time_interval_hours=self.time_interval_hours,
            initial_states=initial_states,
        )
        q_series = np.asarray(q_sim, dtype=float).reshape(-1) * self.flow_factor
        e_series = np.asarray(es, dtype=float).reshape(-1)
        return XAJRunResult(streamflow=q_series.tolist(), evap=e_series.tolist())

    def predict(
        self,
        rainfall: Sequence[float],
        pet: Sequence[float] | None = None,
        params: Sequence[float] | None = None,
        warmup_length: int | None = None,
        initial_states: dict[str, float] | None = None,
    ) -> list[float]:
        return self.simulate(
            rainfall=rainfall,
            pet=pet,
            params=params,
            warmup_length=warmup_length,
            initial_states=initial_states,
        ).streamflow


def nse(obs: Sequence[float], sim: Sequence[float]) -> float:
    obs_arr = np.asarray(obs, dtype=float)
    sim_arr = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs_arr) & np.isfinite(sim_arr)
    if mask.sum() < 2:
        return float("-inf")
    obs_arr = obs_arr[mask]
    sim_arr = sim_arr[mask]
    denom = float(np.sum((obs_arr - np.mean(obs_arr)) ** 2))
    if denom <= 0:
        return float("-inf")
    return float(1.0 - np.sum((sim_arr - obs_arr) ** 2) / denom)


class XAJSpotpyAdapter:
    """spotpy adapter aligned with old_code/XAJ style."""

    def __init__(
        self,
        runner: XAJModelRunner,
        rainfall: Sequence[float],
        pet: Sequence[float],
        observations: Sequence[float],
        train_slice: tuple[int, int],
        warmup_length: int = 0,
    ) -> None:
        self.runner = runner
        self.rainfall = np.asarray(rainfall, dtype=float)
        self.pet = np.asarray(pet, dtype=float)
        self.observations = np.asarray(observations, dtype=float)
        self.train_slice = train_slice
        self.warmup_length = warmup_length
        self.param_names = list(_param_ranges().keys())
        self.params = [
            spotpy.parameter.Uniform(name, 0.0, 1.0)
            for name in self.param_names
        ]

    def parameters(self):
        return spotpy.parameter.generate(self.params)

    def simulation(self, vector):
        return np.asarray(
            self.runner.predict(
                rainfall=self.rainfall,
                pet=self.pet,
                params=np.asarray(vector, dtype=float),
                warmup_length=0,
            ),
            dtype=float,
        )

    def evaluation(self):
        return self.observations

    def objectivefunction(self, simulation, evaluation):
        start, end = self.train_slice
        sim_train = np.asarray(simulation, dtype=float)[start:end]
        obs_train = np.asarray(evaluation, dtype=float)[start:end]
        return -nse(obs_train, sim_train)


def calibrate_xaj_with_spotpy(
    rainfall: Sequence[float],
    pet: Sequence[float],
    observations: Sequence[float],
    train_slice: tuple[int, int],
    basin_area_km2: float = 3300.0,
    repetitions: int = 30,
    ngs: int = 5,
    warmup_length: int = 0,
) -> dict:
    runner = XAJModelRunner(basin_area_km2=basin_area_km2)
    adapter = XAJSpotpyAdapter(
        runner=runner,
        rainfall=rainfall,
        pet=pet,
        observations=observations,
        train_slice=train_slice,
        warmup_length=warmup_length,
    )
    sampler = spotpy.algorithms.sceua(
        adapter,
        dbname="xaj_spotpy_results",
        dbformat="ram",
        save_sim=False,
    )
    sampler.sample(repetitions=repetitions, ngs=ngs, kstop=max(10, ngs))
    results = sampler.getdata()
    best_row = results[np.argmin(results["like1"])]
    best_params = np.array([float(best_row[f"par{name}"]) for name in adapter.param_names], dtype=float)
    train_nse = float(-best_row["like1"])
    return {
        "runner": runner,
        "best_params": best_params,
        "train_nse": train_nse,
        "param_names": adapter.param_names,
        "repetitions": repetitions,
    }
