"""Synthetic interval-by-interval natural gamma logging along completed boreholes."""

from __future__ import annotations

import math

from .geophysics import FIELD_DEFAULTS, local_gamma_response
from .observation_tools import _number, _rng


TABLE_NAME = "downhole_gamma"
TABLE_FIELDS = ("campaign_id hole_id measurement_id from_m to_m depth_m gamma_count_rate_cps "
                "gamma_sigma_cps counting_time_s measurement_method logged_date").split()
DEFAULT_SETTINGS = {"interval_m": 1.0, "sigma_cps": 0.2, "counting_time_s": 60}


def validate_gamma_logging(config, holes):
    settings = config.get("downhole_gamma", {})
    if not isinstance(settings, dict) or not isinstance(settings.get("enabled", False), bool):
        raise ValueError("downhole_gamma: требуется объект с логическим enabled")
    if not settings.get("enabled"):
        return
    step = _number(settings.get("interval_m", DEFAULT_SETTINGS["interval_m"]), "downhole_gamma.interval_m", positive=True)
    if step < 0.000001:
        raise ValueError("Шаг гамма-каротажа должен быть не меньше 0.000001 м")
    _number(settings.get("sigma_cps", DEFAULT_SETTINGS["sigma_cps"]), "downhole_gamma.sigma_cps")
    _number(settings.get("counting_time_s", DEFAULT_SETTINGS["counting_time_s"]), "downhole_gamma.counting_time_s", positive=True)
    if sum(math.ceil(hole["depth_m"] / step) for hole in holes) > 1000000:
        raise ValueError("План превышает миллион измерений гамма-каротажа")


class DownholeGammaLogger:
    def __init__(self, truth, config, seed, mineral_catalog=None):
        self.settings = {**DEFAULT_SETTINGS, **config["downhole_gamma"]}
        self.ideal = config.get("ideal", False)
        self.seed = seed
        self.date = config["date"]
        survey = truth.get("geophysics", {})
        self.model = {**FIELD_DEFAULTS, **survey.get("parameters", {})}
        self.rock_sources = {rock["id"]: rock.get("geophysical_source", {}) for rock in truth["rocks"]}
        self.deposits = {deposit["id"]: deposit for deposit in truth["deposits"]}
        self.mineral_sources = {mineral["id"]: mineral.get("geophysical_source", {})
                                for mineral in (mineral_catalog or {}).get("minerals", ())}
        self.mineral_sources.update(survey.get("mineral_sources", {}))

    def log(self, hole, parts, append):
        step, time = self.settings["interval_m"], self.settings["counting_time_s"]
        rates = [local_gamma_response(part, self.model, self.rock_sources, self.deposits, self.mineral_sources)
                 for part in parts]
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
            sigma = 0 if self.ideal else math.sqrt(self.settings["sigma_cps"]**2 + expected / time)
            identifier = f"{hole['hole_id']}-G{index + 1:04d}"
            value = max(0, expected + _rng(self.seed, "downhole-gamma", identifier).gauss(0, sigma))
            append(TABLE_NAME, hole_id=hole["hole_id"], measurement_id=identifier,
                   from_m=start, to_m=end, depth_m=round((start + end) / 2, 7),
                   gamma_count_rate_cps=round(value, 4), gamma_sigma_cps=round(sigma, 4),
                   counting_time_s=time, measurement_method="synthetic_gamma_logging", logged_date=self.date)
