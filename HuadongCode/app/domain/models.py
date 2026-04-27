"""Domain models shared across tools and core pipelines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ForecastFrame:
    timestamps: list[str]
    rainfall: list[float]
    pet: list[float]
    observed: list[float]
    xinanjiang: list[float]
    gr4j: list[float]
    rf: list[float]
    lstm: list[float]
