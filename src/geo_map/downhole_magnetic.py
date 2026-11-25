"""Synthetic borehole logging of volume magnetic susceptibility (SI)."""

from __future__ import annotations

import math

from .geophysics import local_magnetic_response
from .observation_tools import _number, _rng

TABLE_NAME = "downhole_magnetic"
TABLE_FIELDS = ("campaign_id hole_id measurement_id from_m to_m depth_m magnetic_susceptibility_si "
                "magnetic_sigma_si measurement_method logged_date").split()
DEFAULT_SETTINGS = {"interval_m": 1.0, "sigma_si": 0.00005}


def validate_magnetic_logging(config, holes):
    settings = config.get(TABLE_NAME, {})
    if not isinstance(settings, dict) or not isinstance(settings.get("enabled", False), bool):
        raise ValueError("downhole_magnetic: требуется объект с логическим enabled")
    if not settings.get("enabled"):
        return
    step = _number(settings.get("interval_m", DEFAULT_SETTINGS["interval_m"]),
                   "downhole_magnetic.interval_m", positive=True)
    if step < 0.000001:
        raise ValueError("Шаг магнитного каротажа должен быть не меньше 0.000001 м")
    _number(settings.get("sigma_si", DEFAULT_SETTINGS["sigma_si"]), "downhole_magnetic.sigma_si")
    if sum(math.ceil(hole["depth_m"] / step) for hole in holes) > 1000000:
        raise ValueError("План превышает миллион измерений магнитного каротажа")


class DownholeMagneticLogger:
    def __init__(self, truth, config, seed, mineral_catalog=None):
        self.settings = {**DEFAULT_SETTINGS, **config[TABLE_NAME]}
        self.sigma = 0 if config.get("ideal", False) else self.settings["sigma_si"]
        self.seed = seed
        self.date = config["date"]
        self.rocks = {rock["id"]: rock.get("geophysical_source", {}) for rock in truth["rocks"]}
        self.deposits = {deposit["id"]: deposit for deposit in truth["deposits"]}
        self.minerals = {mineral["id"]: mineral.get("geophysical_source", {})
                         for mineral in (mineral_catalog or {}).get("minerals", ())}
        self.minerals.update(truth.get("geophysics", {}).get("mineral_sources", {}))

    def log(self, hole, parts, append):
        step = self.settings["interval_m"]
        rates = [local_magnetic_response(part, self.rocks, self.deposits, self.minerals) for part in parts]
        first = 0
        for index in range(math.ceil(hole["depth_m"] / step)):
            start = round(index * step, 6)
            if start >= hole["depth_m"]:
                break
            end = min(hole["depth_m"], round((index + 1) * step, 6))
            while parts[first]["to_m"] <= start:
                first += 1
            weighted = 0.0
            for j in range(first, len(parts)):
                part = parts[j]
                if part["from_m"] >= end:
                    break
                overlap = min(end, part["to_m"]) - max(start, part["from_m"])
                weighted += rates[j] * overlap
            expected = weighted / (end - start)
            identifier = f"{hole['hole_id']}-M{index + 1:04d}"
            measured = expected + _rng(self.seed, "downhole-magnetic", identifier).gauss(0, self.sigma)
            append(TABLE_NAME, hole_id=hole["hole_id"], measurement_id=identifier,
                   from_m=start, to_m=end, depth_m=round((start + end) / 2, 7),
                   magnetic_susceptibility_si=round(measured, 9), magnetic_sigma_si=self.sigma,
                   measurement_method="synthetic_magnetic_logging", logged_date=self.date)
