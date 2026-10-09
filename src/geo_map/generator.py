from __future__ import annotations

import hashlib
import json
import math
import secrets
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_config(
    generation_path: str | Path,
    rocks_path: str | Path,
    minerals_path: str | Path,
) -> dict[str, Any]:
    """Load generation settings, rocks and minerals from separate files."""
    config = deepcopy(_read_json(generation_path))
    rocks_config = _read_json(rocks_path)
    minerals_config = _read_json(minerals_path)
    if set(rocks_config) != {"rocks"}:
        raise ValueError("rocks.json должен содержать только раздел rocks")
    if set(minerals_config) != {"minerals"}:
        raise ValueError("minerals.json должен содержать только раздел minerals")
    config["rocks"] = rocks_config["rocks"]
    config["minerals"] = minerals_config["minerals"]
    _validate_config(config)
    return config


def _range_pair(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"Параметр {name} должен быть диапазоном [min, max]")
    low, high = float(value[0]), float(value[1])
    if low > high:
        raise ValueError(f"В диапазоне {name} min не может быть больше max")
    return low, high


def _validate_config(config: dict[str, Any]) -> None:
    required = {"map", "rocks", "minerals", "geology", "deposit_generation"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"Отсутствуют разделы конфигурации: {sorted(missing)}")

    map_config = config["map"]
    for key in ("width_cells", "height_cells", "depth_cells", "cell_size_m", "depth_step_m"):
        if int(map_config.get(key, 0)) <= 0:
            raise ValueError(f"Параметр map.{key} должен быть положительным")

    rocks = config["rocks"]
    if not rocks:
        raise ValueError("Справочник пород не может быть пустым")
    rock_ids = [rock["id"] for rock in rocks]
    if len(rock_ids) != len(set(rock_ids)):
        raise ValueError("Идентификаторы пород должны быть уникальными")
    for rock in rocks:
        _range_pair(rock.get("density_g_cm3"), f"rocks.{rock['id']}.density_g_cm3")
        _range_pair(rock.get("porosity_percent"), f"rocks.{rock['id']}.porosity_percent")

    geology = config["geology"]
    layer_low, layer_high = _range_pair(geology.get("layer_count"), "geology.layer_count")
    if (
        int(layer_low) != layer_low
        or int(layer_high) != layer_high
        or int(layer_low) < 2
    ):
        raise ValueError("Количество слоёв должно быть целым и не меньше двух")
    surface_id = geology.get("surface_rock_id")
    subsurface_ids = geology.get("subsurface_rock_ids", [])
    unknown_ids = {surface_id, *subsurface_ids} - set(rock_ids)
    if unknown_ids:
        raise ValueError(f"Неизвестные породы в настройках генерации: {sorted(unknown_ids)}")
    if not subsurface_ids:
        raise ValueError("Нужна хотя бы одна подземная порода")

    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    _, surface_high = _range_pair(
        geology.get("surface_thickness_m"), "geology.surface_thickness_m"
    )
    minimum = float(geology.get("minimum_layer_thickness_m", 0))
    if minimum <= 0:
        raise ValueError("geology.minimum_layer_thickness_m должен быть положительным")
    if surface_high + (int(layer_high) - 1) * minimum > total_depth:
        raise ValueError("Для заданной глубины невозможно разместить максимальное число слоёв")
    _range_pair(geology.get("boundary_variation_m"), "geology.boundary_variation_m")
    _range_pair(geology.get("wave_x"), "geology.wave_x")
    _range_pair(geology.get("wave_y"), "geology.wave_y")

    deposit_generation = config["deposit_generation"]
    count_low, count_high = _range_pair(
        deposit_generation.get("count"), "deposit_generation.count"
    )
    if (
        int(count_low) != count_low
        or int(count_high) != count_high
        or int(count_low) < 0
    ):
        raise ValueError("Количество месторождений не может быть отрицательным")
    minerals = config["minerals"]
    if not minerals and count_low > 0:
        raise ValueError("Для генерации месторождений нужен хотя бы один тип")
    if count_high > len(minerals):
        raise ValueError(
            "Максимальное количество месторождений не должно превышать число "
            "видов полезных ископаемых"
        )
    mineral_ids = [mineral["id"] for mineral in minerals]
    if len(mineral_ids) != len(set(mineral_ids)):
        raise ValueError("Идентификаторы полезных ископаемых должны быть уникальными")
    for index, mineral in enumerate(minerals):
        if float(mineral.get("weight", 0)) <= 0:
            raise ValueError(f"minerals[{index}].weight должен быть положительным")
        for key in (
            "radius_x_m",
            "radius_y_m",
            "radius_z_m",
            "max_concentration_percent",
        ):
            low, _ = _range_pair(mineral.get(key), f"minerals[{index}].{key}")
            if low <= 0:
                raise ValueError(f"Диапазон {key} должен быть положительным")


def _stable_unit(seed: int, *parts: object) -> float:
    """Return a deterministic number in [0, 1] independent of Python hash randomization."""
    payload = ":".join(str(part) for part in (seed, *parts)).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / ((1 << 64) - 1)


def _sample_range(seed: int, low: float, high: float, *parts: object) -> float:
    return low + (high - low) * _stable_unit(seed, *parts)


def _sample_int(seed: int, low: int, high: int, *parts: object) -> int:
    if low == high:
        return low
    value = int(_stable_unit(seed, *parts) * (high - low + 1))
    return min(high, low + value)


def _round_to_step(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _partition_steps(
    total_steps: int,
    count: int,
    minimum_steps: int,
    seed: int,
) -> list[int]:
    """Split a depth into random positive layer thicknesses."""
    free_steps = total_steps - count * minimum_steps
    if free_steps < 0:
        raise ValueError("Недостаточно глубины для случайного набора слоёв")
    weights = [0.25 + _stable_unit(seed, "layer-weight", index) for index in range(count)]
    weight_sum = sum(weights)
    exact = [free_steps * weight / weight_sum for weight in weights]
    allocated = [math.floor(value) for value in exact]
    leftover = free_steps - sum(allocated)
    order = sorted(range(count), key=lambda index: exact[index] - allocated[index], reverse=True)
    for index in order[:leftover]:
        allocated[index] += 1
    return [minimum_steps + value for value in allocated]


def _generate_layers(config: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    map_config = config["map"]
    geology = config["geology"]
    step = int(map_config["depth_step_m"])
    total_steps = int(map_config["depth_cells"])
    layer_low, layer_high = (int(value) for value in geology["layer_count"])
    layer_count = _sample_int(seed, layer_low, layer_high, "layer-count")

    surface_low, surface_high = geology["surface_thickness_m"]
    surface_low_steps = max(1, math.ceil(surface_low / step))
    surface_high_steps = max(surface_low_steps, math.floor(surface_high / step))
    surface_steps = _sample_int(
        seed, surface_low_steps, surface_high_steps, "surface-thickness"
    )
    minimum_steps = max(1, math.ceil(geology["minimum_layer_thickness_m"] / step))
    subsurface_thicknesses = _partition_steps(
        total_steps - surface_steps,
        layer_count - 1,
        minimum_steps,
        seed,
    )
    thicknesses = [surface_steps, *subsurface_thicknesses]

    rock_sequence = [geology["surface_rock_id"]]
    candidates = list(geology["subsurface_rock_ids"])
    unused_candidates = candidates.copy()
    for index in range(1, layer_count):
        if not unused_candidates:
            unused_candidates = candidates.copy()
        available = [
            rock_id for rock_id in unused_candidates if rock_id != rock_sequence[-1]
        ] or unused_candidates
        selected = _sample_int(seed, 0, len(available) - 1, "layer-rock", index)
        selected_rock = available[selected]
        rock_sequence.append(selected_rock)
        unused_candidates.remove(selected_rock)

    variation_low, variation_high = geology["boundary_variation_m"]
    wave_x_low, wave_x_high = geology["wave_x"]
    wave_y_low, wave_y_high = geology["wave_y"]
    layers: list[dict[str, Any]] = []
    bottom_steps = 0
    for index, (rock_id, thickness_steps) in enumerate(zip(rock_sequence, thicknesses, strict=True)):
        bottom_steps += thickness_steps
        layer: dict[str, Any] = {
            "rock_id": rock_id,
            "base_bottom_depth_m": bottom_steps * step,
        }
        if index < layer_count - 1:
            layer.update(
                {
                    "variation_m": round(
                        _sample_range(seed, variation_low, variation_high, "variation", index), 3
                    ),
                    "wave_x": round(
                        _sample_range(seed, wave_x_low, wave_x_high, "wave-x", index), 5
                    ),
                    "wave_y": round(
                        _sample_range(seed, wave_y_low, wave_y_high, "wave-y", index), 5
                    ),
                    "phase": round(_sample_range(seed, 0, math.tau, "phase", index), 5),
                }
            )
        layers.append(layer)
    return layers


def _layer_boundaries(
    map_config: dict[str, Any],
    layers: list[dict[str, Any]],
    x_index: int,
    y_index: int,
    seed: int,
) -> list[int]:
    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    step = map_config["depth_step_m"]
    boundaries: list[int] = []
    previous = 0
    layer_count = len(layers)

    for index, layer in enumerate(layers[:-1]):
        base = float(layer["base_bottom_depth_m"])
        variation = float(layer["variation_m"])
        wave_x = float(layer["wave_x"])
        wave_y = float(layer["wave_y"])
        phase = float(layer["phase"])
        smooth = (
            0.55 * math.sin(x_index * wave_x + phase)
            + 0.35 * math.cos(y_index * wave_y - phase)
            + 0.20 * math.sin((x_index + y_index) * 0.075 + phase * 0.5)
        )
        local_noise = (_stable_unit(seed, "boundary", index, x_index, y_index) - 0.5) * step
        boundary = _round_to_step(base + variation * smooth + local_noise, step)

        remaining_layers = layer_count - index - 1
        minimum = previous + step
        maximum = total_depth - remaining_layers * step
        boundary = max(minimum, min(maximum, boundary))
        boundaries.append(boundary)
        previous = boundary

    boundaries.append(total_depth)
    return boundaries


def _make_intervals(
    rocks: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    boundaries: list[int],
    x_index: int,
    y_index: int,
    seed: int,
) -> list[dict[str, Any]]:
    intervals: list[dict[str, Any]] = []
    top = 0
    rocks_by_id = {rock["id"]: rock for rock in rocks}

    for index, (layer, bottom) in enumerate(zip(layers, boundaries, strict=True)):
        rock = rocks_by_id[layer["rock_id"]]
        density_low, density_high = rock["density_g_cm3"]
        porosity_low, porosity_high = rock["porosity_percent"]
        intervals.append(
            {
                "from_depth_m": top,
                "to_depth_m": bottom,
                "rock_id": rock["id"],
                "properties": {
                    "density_g_cm3": round(
                        _sample_range(
                            seed, density_low, density_high, "density", x_index, y_index, index
                        ),
                        3,
                    ),
                    "porosity_percent": round(
                        _sample_range(
                            seed, porosity_low, porosity_high, "porosity", x_index, y_index, index
                        ),
                        3,
                    ),
                },
                "origin": "generated",
            }
        )
        top = bottom
    return intervals


def _select_deposit_types(
    seed: int,
    deposit_types: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    """Choose weighted mineral types without repeats for one map."""
    available = deposit_types.copy()
    selected: list[dict[str, Any]] = []
    for deposit_index in range(count):
        total_weight = sum(float(item["weight"]) for item in available)
        target = _stable_unit(seed, "deposit-type", deposit_index) * total_weight
        accumulated = 0.0
        chosen = available[-1]
        for item in available:
            accumulated += float(item["weight"])
            if target <= accumulated:
                chosen = item
                break
        selected.append(chosen)
        available.remove(chosen)
    return selected


def _center_inside_extent(
    seed: int,
    extent: float,
    radius: float,
    axis: str,
    deposit_index: int,
) -> float:
    usable_radius = min(radius, extent / 2)
    low = usable_radius
    high = extent - usable_radius
    return round(_sample_range(seed, low, high, "deposit-center", deposit_index, axis), 2)


def _generate_deposits(config: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    map_config = config["map"]
    generation = config["deposit_generation"]
    count_low, count_high = (int(value) for value in generation["count"])
    count = _sample_int(seed, count_low, count_high, "deposit-count")
    types = config["minerals"]
    selected_types = _select_deposit_types(seed, types, count)
    width_m = map_config["width_cells"] * map_config["cell_size_m"]
    height_m = map_config["height_cells"] * map_config["cell_size_m"]
    depth_m = map_config["depth_cells"] * map_config["depth_step_m"]
    deposits: list[dict[str, Any]] = []

    for index, definition in enumerate(selected_types):
        radius_x = min(
            width_m / 2,
            _sample_range(seed, *definition["radius_x_m"], "deposit-radius", index, "x"),
        )
        radius_y = min(
            height_m / 2,
            _sample_range(seed, *definition["radius_y_m"], "deposit-radius", index, "y"),
        )
        radius_z = min(
            depth_m / 2,
            _sample_range(seed, *definition["radius_z_m"], "deposit-radius", index, "z"),
        )
        deposit_number = index + 1
        deposits.append(
            {
                "id": f"{definition['id']}_deposit_{deposit_number}",
                "mineral_id": definition["id"],
                "name": f"{definition['name']} №{deposit_number}",
                "mineral": definition["mineral"],
                "color": definition["color"],
                "center_m": [
                    _center_inside_extent(seed, width_m, radius_x, "x", index),
                    _center_inside_extent(seed, height_m, radius_y, "y", index),
                    _center_inside_extent(seed, depth_m, radius_z, "z", index),
                ],
                "radii_m": [round(radius_x, 2), round(radius_y, 2), round(radius_z, 2)],
                "max_concentration_percent": round(
                    _sample_range(
                        seed,
                        *definition["max_concentration_percent"],
                        "deposit-concentration",
                        index,
                    ),
                    3,
                ),
                "display_threshold_percent": definition["display_threshold_percent"],
                "origin": "generated",
            }
        )
    return deposits


def _deposits_for_cell(
    map_config: dict[str, Any],
    deposits: list[dict[str, Any]],
    x_index: int,
    y_index: int,
) -> list[dict[str, Any]]:
    cell_size = map_config["cell_size_m"]
    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    x = (x_index + 0.5) * cell_size
    y = (y_index + 0.5) * cell_size
    result: list[dict[str, Any]] = []

    for deposit in deposits:
        center_x, center_y, center_z = deposit["center_m"]
        radius_x, radius_y, radius_z = deposit["radii_m"]
        horizontal_distance = ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2
        if horizontal_distance >= 1:
            continue

        half_height = radius_z * math.sqrt(1 - horizontal_distance)
        top = max(0.0, center_z - half_height)
        bottom = min(float(total_depth), center_z + half_height)
        if bottom <= top:
            continue

        max_grade = deposit["max_concentration_percent"] * (1 - horizontal_distance)
        threshold = deposit["display_threshold_percent"]
        if max_grade < threshold:
            continue
        average_grade = max(threshold, max_grade * 0.62)
        result.append(
            {
                "deposit_id": deposit["id"],
                "mineral": deposit["mineral"],
                "from_depth_m": round(top, 2),
                "to_depth_m": round(bottom, 2),
                "average_concentration_percent": round(average_grade, 3),
                "maximum_concentration_percent": round(max_grade, 3),
            }
        )
    return result


def generate_map(config: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """Generate a complete synthetic ground-truth map in interval form."""
    _validate_config(config)
    config = deepcopy(config)
    map_config = config["map"]
    effective_seed = secrets.randbits(63) if seed is None else int(seed)
    map_config["seed"] = effective_seed
    layers = _generate_layers(config, effective_seed)
    deposits = _generate_deposits(config, effective_seed)

    cells: list[dict[str, Any]] = []
    rock_interval_counts = {rock["id"]: 0 for rock in config["rocks"]}
    mineralized_cells = 0

    for y_index in range(map_config["height_cells"]):
        for x_index in range(map_config["width_cells"]):
            boundaries = _layer_boundaries(
                map_config, layers, x_index, y_index, effective_seed
            )
            intervals = _make_intervals(
                config["rocks"], layers, boundaries, x_index, y_index, effective_seed
            )
            mineralization = _deposits_for_cell(
                map_config, deposits, x_index, y_index
            )
            for interval in intervals:
                rock_interval_counts[interval["rock_id"]] += 1
            if mineralization:
                mineralized_cells += 1
            cells.append(
                {
                    "x_index": x_index,
                    "y_index": y_index,
                    "x_m": x_index * map_config["cell_size_m"],
                    "y_m": y_index * map_config["cell_size_m"],
                    "surface_elevation_m": 0,
                    "intervals": intervals,
                    "mineralization": mineralization,
                }
            )

    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    return {
        "schema_version": "1.1",
        "map_kind": "synthetic_ground_truth",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": effective_seed,
        "dimensions": {
            "width_cells": map_config["width_cells"],
            "height_cells": map_config["height_cells"],
            "depth_cells": map_config["depth_cells"],
            "cell_size_m": map_config["cell_size_m"],
            "depth_step_m": map_config["depth_step_m"],
            "width_m": map_config["width_cells"] * map_config["cell_size_m"],
            "height_m": map_config["height_cells"] * map_config["cell_size_m"],
            "depth_m": total_depth,
        },
        "rocks": config["rocks"],
        "geological_layers": layers,
        "deposits": deposits,
        "statistics": {
            "cell_count": len(cells),
            "layer_count": len(layers),
            "deposit_count": len(deposits),
            "mineralized_cell_count": mineralized_cells,
            "rock_interval_counts": rock_interval_counts,
        },
        "cells": cells,
    }


def save_map(data: dict[str, Any], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return output_path
