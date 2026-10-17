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
    stratigraphic_groups = geology.get("stratigraphic_groups", [])
    if not stratigraphic_groups:
        raise ValueError("Нужна хотя бы одна стратиграфическая группа")
    group_ids = [group["id"] for group in stratigraphic_groups]
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("Идентификаторы стратиграфических групп должны быть уникальными")

    subsurface_ids: list[str] = []
    minimum_subsurface_layers = 0
    for index, group in enumerate(stratigraphic_groups):
        group_rock_ids = group.get("rock_ids", [])
        if not group_rock_ids:
            raise ValueError(f"Стратиграфическая группа {group_ids[index]} не может быть пустой")
        minimum_layers = group.get("minimum_layers", 1)
        if not isinstance(minimum_layers, int) or minimum_layers < 0:
            raise ValueError("minimum_layers должен быть неотрицательным целым числом")
        if minimum_layers > len(group_rock_ids):
            raise ValueError("minimum_layers не может превышать число пород в группе")
        minimum_subsurface_layers += minimum_layers
        subsurface_ids.extend(group_rock_ids)

    if len(subsurface_ids) != len(set(subsurface_ids)):
        raise ValueError("Одна порода не может входить в несколько стратиграфических групп")
    unknown_ids = {surface_id, *subsurface_ids} - set(rock_ids)
    if unknown_ids:
        raise ValueError(f"Неизвестные породы в настройках генерации: {sorted(unknown_ids)}")
    if surface_id in subsurface_ids:
        raise ValueError("Поверхностная порода не должна входить в подземные группы")
    if int(layer_low) - 1 < minimum_subsurface_layers:
        raise ValueError("Минимального числа слоёв недостаточно для обязательных групп")
    if int(layer_high) - 1 > len(subsurface_ids):
        raise ValueError("Максимальное число слоёв превышает число доступных пород")

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

    fault_generation = geology.get("fault_generation", {})
    fault_count_low, fault_count_high = _range_pair(
        fault_generation.get("count"), "geology.fault_generation.count"
    )
    if (
        int(fault_count_low) != fault_count_low
        or int(fault_count_high) != fault_count_high
        or int(fault_count_low) < 0
    ):
        raise ValueError("Количество разломов должно быть неотрицательным целым числом")
    dip_low, dip_high = _range_pair(
        fault_generation.get("dip_deg"), "geology.fault_generation.dip_deg"
    )
    if dip_low <= 0 or dip_high > 90:
        raise ValueError("Угол падения разлома должен находиться в диапазоне (0, 90]")
    displacement_low, _ = _range_pair(
        fault_generation.get("displacement_m"),
        "geology.fault_generation.displacement_m",
    )
    influence_low, _ = _range_pair(
        fault_generation.get("influence_width_m"),
        "geology.fault_generation.influence_width_m",
    )
    if displacement_low <= 0 or influence_low <= 0:
        raise ValueError("Смещение и ширина зоны влияния разлома должны быть положительными")

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
    for key in (
        "shape_irregularity",
        "vertical_irregularity",
        "noise_scale_cells",
        "concentration_variation",
    ):
        low, high = _range_pair(
            deposit_generation.get(key), f"deposit_generation.{key}"
        )
        if low <= 0:
            raise ValueError(f"Параметр deposit_generation.{key} должен быть положительным")
        if key != "noise_scale_cells" and high >= 1:
            raise ValueError(f"Параметр deposit_generation.{key} должен быть меньше 1")
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
    generatable_rock_ids = {surface_id, *subsurface_ids}
    allowed_controls = {"host", "stratiform", "contact", "fault", "intrusive"}
    width_m = map_config["width_cells"] * map_config["cell_size_m"]
    height_m = map_config["height_cells"] * map_config["cell_size_m"]
    for index, mineral in enumerate(minerals):
        if float(mineral.get("weight", 0)) <= 0:
            raise ValueError(f"minerals[{index}].weight должен быть положительным")
        depth_low, depth_high = _range_pair(
            mineral.get("allowed_depth_m"), f"minerals[{index}].allowed_depth_m"
        )
        if depth_low < 0 or depth_high > total_depth or depth_low == depth_high:
            raise ValueError(
                "Допустимая глубина ископаемого должна находиться внутри карты"
            )
        for key in ("radius_x_m", "radius_y_m", "radius_z_m"):
            low, _ = _range_pair(mineral.get(key), f"minerals[{index}].{key}")
            if low <= 0:
                raise ValueError(f"Диапазон {key} должен быть положительным")
            available_size = {
                "radius_x_m": width_m,
                "radius_y_m": height_m,
            }.get(key)
            if available_size is not None and low * 2 > available_size:
                raise ValueError(
                    f"Минимальный {key} для {mineral['id']} не помещается на карте"
                )
        _, radius_z_high = _range_pair(
            mineral.get("radius_z_m"), f"minerals[{index}].radius_z_m"
        )
        if radius_z_high * 2 > depth_high - depth_low:
            raise ValueError(
                "Вертикальный радиус месторождения не помещается в допустимый диапазон глубины"
            )

        grade = mineral.get("grade")
        if not isinstance(grade, dict):
            raise ValueError(f"minerals[{index}].grade должен быть объектом")
        grade_low, grade_high = _range_pair(
            grade.get("maximum"), f"minerals[{index}].grade.maximum"
        )
        threshold = float(grade.get("display_threshold", 0))
        if grade_low <= 0 or threshold <= 0 or threshold > grade_high:
            raise ValueError(
                f"minerals[{index}].grade должен задавать положительные значения и порог"
            )
        maximum_variation = float(deposit_generation["concentration_variation"][1])
        if threshold > grade_low * (1 - maximum_variation):
            raise ValueError(
                f"Порог {mineral['id']} слишком высок и может скрыть центр месторождения"
            )
        if not isinstance(grade.get("unit"), str) or not grade["unit"].strip():
            raise ValueError(f"minerals[{index}].grade.unit не может быть пустым")

        model = mineral.get("geological_model")
        if not isinstance(model, dict):
            raise ValueError(f"minerals[{index}].geological_model должен быть объектом")
        control = model.get("control")
        if control not in allowed_controls:
            raise ValueError(
                f"minerals[{index}].geological_model.control должен быть одним из "
                f"{sorted(allowed_controls)}"
            )
        host_ids = model.get("host_rock_ids")
        if not isinstance(host_ids, list) or not host_ids:
            raise ValueError(
                f"minerals[{index}].geological_model.host_rock_ids не может быть пустым"
            )
        if not all(isinstance(rock_id, str) for rock_id in host_ids):
            raise ValueError(
                f"minerals[{index}].geological_model.host_rock_ids должен содержать строки"
            )
        if len(host_ids) != len(set(host_ids)):
            raise ValueError(
                f"minerals[{index}].geological_model.host_rock_ids содержит дубликаты"
            )
        unknown_hosts = set(host_ids) - set(rock_ids)
        if unknown_hosts:
            raise ValueError(
                f"Неизвестные породы-хозяева для {mineral['id']}: {sorted(unknown_hosts)}"
            )

        if control == "intrusive":
            body_rock_id = model.get("body_rock_id")
            if body_rock_id not in rock_ids:
                raise ValueError(
                    f"Интрузивная модель {mineral['id']} должна задавать известный body_rock_id"
                )
            if not set(host_ids) & generatable_rock_ids:
                raise ValueError(
                    f"Вмещающие породы {mineral['id']} не входят в стратиграфию"
                )
        elif not set(host_ids) & generatable_rock_ids:
            raise ValueError(
                f"Породы-хозяева {mineral['id']} не входят в генерируемую стратиграфию"
            )

        contact_ids = model.get("contact_rock_ids", [])
        if not isinstance(contact_ids, list):
            raise ValueError(
                f"minerals[{index}].geological_model.contact_rock_ids должен быть списком"
            )
        if not all(isinstance(rock_id, str) for rock_id in contact_ids):
            raise ValueError(
                f"minerals[{index}].geological_model.contact_rock_ids должен содержать строки"
            )
        if contact_ids:
            if len(contact_ids) != len(set(contact_ids)):
                raise ValueError(
                    f"minerals[{index}].geological_model.contact_rock_ids содержит дубликаты"
                )
            unknown_contacts = set(contact_ids) - set(rock_ids)
            if unknown_contacts:
                raise ValueError(
                    f"Неизвестные контактные породы для {mineral['id']}: "
                    f"{sorted(unknown_contacts)}"
                )
        if control == "contact":
            if not contact_ids:
                raise ValueError(
                    f"Контактная модель {mineral['id']} требует contact_rock_ids"
                )
            if not set(contact_ids) & generatable_rock_ids:
                raise ValueError(
                    f"Контактные породы {mineral['id']} не входят в стратиграфию"
                )
            contact_buffer = float(model.get("contact_buffer_m", 0))
            if contact_buffer <= 0:
                raise ValueError(
                    f"Контактная модель {mineral['id']} требует положительный contact_buffer_m"
                )
        if control == "fault" and fault_count_high < 1:
            raise ValueError(
                f"Разломная модель {mineral['id']} требует генерацию хотя бы одного разлома"
            )


def _stable_unit(seed: int, *parts: object) -> float:
    """Return a deterministic number in [0, 1] independent of Python hash randomization."""
    payload = ":".join(str(part) for part in (seed, *parts)).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / ((1 << 64) - 1)


def _smooth_noise_2d(
    seed: int,
    x: float,
    y: float,
    scale: float,
    *parts: object,
) -> float:
    """Deterministic smoothly interpolated value noise in [0, 1]."""
    grid_x = x / scale
    grid_y = y / scale
    x0 = math.floor(grid_x)
    y0 = math.floor(grid_y)
    fraction_x = grid_x - x0
    fraction_y = grid_y - y0
    fade_x = fraction_x * fraction_x * (3 - 2 * fraction_x)
    fade_y = fraction_y * fraction_y * (3 - 2 * fraction_y)

    value_00 = _stable_unit(seed, "smooth-noise", *parts, x0, y0)
    value_10 = _stable_unit(seed, "smooth-noise", *parts, x0 + 1, y0)
    value_01 = _stable_unit(seed, "smooth-noise", *parts, x0, y0 + 1)
    value_11 = _stable_unit(seed, "smooth-noise", *parts, x0 + 1, y0 + 1)
    top = value_00 + (value_10 - value_00) * fade_x
    bottom = value_01 + (value_11 - value_01) * fade_x
    return top + (bottom - top) * fade_y


def _fractal_noise_2d(
    seed: int,
    x: float,
    y: float,
    scale: float,
    *parts: object,
) -> float:
    coarse = _smooth_noise_2d(seed, x, y, scale, *parts, "coarse")
    detail = _smooth_noise_2d(seed, x, y, max(0.75, scale * 0.43), *parts, "detail")
    return 0.72 * coarse + 0.28 * detail


def _sample_range(seed: int, low: float, high: float, *parts: object) -> float:
    return low + (high - low) * _stable_unit(seed, *parts)


def _sample_int(seed: int, low: int, high: int, *parts: object) -> int:
    if low == high:
        return low
    value = int(_stable_unit(seed, *parts) * (high - low + 1))
    return min(high, low + value)


def _generate_faults(
    map_config: dict[str, Any],
    geology: dict[str, Any],
    seed: int,
) -> list[dict[str, Any]]:
    """Generate fault traces that displace layers and may control mineralization."""
    settings = geology["fault_generation"]
    count_low, count_high = (int(value) for value in settings["count"])
    count = _sample_int(seed, count_low, count_high, "fault-count")
    width_m = map_config["width_cells"] * map_config["cell_size_m"]
    height_m = map_config["height_cells"] * map_config["cell_size_m"]
    step = int(map_config["depth_step_m"])
    faults: list[dict[str, Any]] = []

    for index in range(count):
        strike = round(_sample_range(seed, 0, 180, "fault-strike", index), 2)
        displacement = _sample_range(
            seed,
            *settings["displacement_m"],
            "fault-displacement",
            index,
        )
        direction = -1 if _stable_unit(seed, "fault-direction", index) < 0.5 else 1
        signed_displacement = direction * max(
            step, _round_to_step(displacement, step)
        )
        faults.append(
            {
                "id": f"fault_{index + 1}",
                "trace_center_m": [
                    round(
                        _sample_range(
                            seed, width_m * 0.2, width_m * 0.8, "fault-center-x", index
                        ),
                        2,
                    ),
                    round(
                        _sample_range(
                            seed,
                            height_m * 0.2,
                            height_m * 0.8,
                            "fault-center-y",
                            index,
                        ),
                        2,
                    ),
                ],
                "strike_deg": strike,
                "dip_deg": round(
                    _sample_range(seed, *settings["dip_deg"], "fault-dip", index), 2
                ),
                "dip_direction_deg": round((strike + 90) % 360, 2),
                "vertical_displacement_m": signed_displacement,
                "influence_width_m": round(
                    _sample_range(
                        seed,
                        *settings["influence_width_m"],
                        "fault-influence-width",
                        index,
                    ),
                    2,
                ),
                "origin": "generated",
            }
        )
    return faults


def _fault_signed_distance_m(
    fault: dict[str, Any],
    x_m: float,
    y_m: float,
    depth_m: float = 0.0,
) -> float:
    """Signed horizontal distance to a dipping fault plane at a given depth."""
    center_x, center_y = fault["trace_center_m"]
    angle = math.radians(fault["strike_deg"])
    normal_x = -math.sin(angle)
    normal_y = math.cos(angle)
    surface_distance = (x_m - center_x) * normal_x + (y_m - center_y) * normal_y
    dip = math.radians(float(fault["dip_deg"]))
    if math.isclose(dip, math.pi / 2):
        return surface_distance
    trace_shift = depth_m / math.tan(dip)
    return surface_distance - trace_shift


def _fault_boundary_offset_m(
    faults: list[dict[str, Any]], x_m: float, y_m: float, depth_m: float
) -> float:
    return sum(
        fault["vertical_displacement_m"]
        for fault in faults
        if _fault_signed_distance_m(fault, x_m, y_m, depth_m) >= 0
    )


def _fault_zone_depth_range(
    fault: dict[str, Any],
    x_m: float,
    y_m: float,
    depth_low: float,
    depth_high: float,
) -> tuple[float, float] | None:
    """Clip a vertical interval to the three-dimensional fault influence zone."""
    surface_distance = _fault_signed_distance_m(fault, x_m, y_m)
    influence_width = float(fault["influence_width_m"])
    dip = math.radians(float(fault["dip_deg"]))
    if math.isclose(dip, math.pi / 2):
        return (
            (depth_low, depth_high)
            if abs(surface_distance) <= influence_width
            else None
        )

    tangent = math.tan(dip)
    zone_low = (surface_distance - influence_width) * tangent
    zone_high = (surface_distance + influence_width) * tangent
    clipped_low = max(depth_low, min(zone_low, zone_high))
    clipped_high = min(depth_high, max(zone_low, zone_high))
    if clipped_low >= clipped_high:
        return None
    return clipped_low, clipped_high


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


def _select_stratified_rocks(
    geology: dict[str, Any],
    layer_count: int,
    seed: int,
) -> list[tuple[str, str]]:
    """Choose unique rocks while preserving the configured shallow-to-deep order."""
    groups = geology["stratigraphic_groups"]
    counts = [int(group.get("minimum_layers", 1)) for group in groups]
    remaining = layer_count - sum(counts)

    for allocation_index in range(remaining):
        available_groups = [
            index
            for index, group in enumerate(groups)
            if counts[index] < len(group["rock_ids"])
        ]
        selected_index = _sample_int(
            seed,
            0,
            len(available_groups) - 1,
            "stratigraphy-allocation",
            allocation_index,
        )
        counts[available_groups[selected_index]] += 1

    selected: list[tuple[str, str]] = []
    for group, count in zip(groups, counts, strict=True):
        available_rocks = list(group["rock_ids"])
        for position in range(count):
            selected_index = _sample_int(
                seed,
                0,
                len(available_rocks) - 1,
                "stratigraphy-rock",
                group["id"],
                position,
            )
            selected.append((available_rocks.pop(selected_index), group["id"]))
    return selected


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

    rock_sequence = [
        (geology["surface_rock_id"], "surface"),
        *_select_stratified_rocks(geology, layer_count - 1, seed),
    ]

    variation_low, variation_high = geology["boundary_variation_m"]
    wave_x_low, wave_x_high = geology["wave_x"]
    wave_y_low, wave_y_high = geology["wave_y"]
    layers: list[dict[str, Any]] = []
    bottom_steps = 0
    for index, ((rock_id, group_id), thickness_steps) in enumerate(
        zip(rock_sequence, thicknesses, strict=True)
    ):
        bottom_steps += thickness_steps
        layer: dict[str, Any] = {
            "rock_id": rock_id,
            "stratigraphic_group": group_id,
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
    geology: dict[str, Any],
    layers: list[dict[str, Any]],
    faults: list[dict[str, Any]],
    x_index: int,
    y_index: int,
    seed: int,
) -> list[int]:
    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    step = map_config["depth_step_m"]
    boundaries: list[int] = []
    previous = 0
    layer_count = len(layers)
    minimum_layer_thickness = max(
        step,
        math.ceil(float(geology["minimum_layer_thickness_m"]) / step) * step,
    )
    x_m = (x_index + 0.5) * map_config["cell_size_m"]
    y_m = (y_index + 0.5) * map_config["cell_size_m"]

    for index, layer in enumerate(layers[:-1]):
        base = float(layer["base_bottom_depth_m"])
        variation = float(layer["variation_m"])
        wave_x = float(layer["wave_x"])
        wave_y = float(layer["wave_y"])
        phase = float(layer["phase"])
        if index == 0:
            # Loose surface material drapes over the bedrock and keeps the
            # configured thickness instead of inheriting every fault throw.
            boundary = _round_to_step(base, step)
        else:
            smooth = (
                0.55 * math.sin(x_index * wave_x + phase)
                + 0.35 * math.cos(y_index * wave_y - phase)
                + 0.20 * math.sin((x_index + y_index) * 0.075 + phase * 0.5)
            )
            local_noise = (
                _stable_unit(seed, "boundary", index, x_index, y_index) - 0.5
            ) * step
            fault_offset = _fault_boundary_offset_m(
                faults, x_m, y_m, base
            )
            boundary = _round_to_step(
                base + variation * smooth + local_noise + fault_offset,
                step,
            )

        remaining_layers = layer_count - index - 1
        minimum = previous + (step if index == 0 else minimum_layer_thickness)
        maximum = total_depth - remaining_layers * minimum_layer_thickness
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


def _definition_candidates(
    definition: dict[str, Any],
    cells: list[dict[str, Any]],
    faults: list[dict[str, Any]],
    map_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return actual geological settings where a deposit type can be placed."""
    model = definition["geological_model"]
    control = model["control"]
    host_ids = set(model["host_rock_ids"])
    contact_ids = set(model.get("contact_rock_ids", []))
    depth_low, depth_high = definition["allowed_depth_m"]
    minimum_radius_z = float(definition["radius_z_m"][0])
    center_floor = depth_low + minimum_radius_z
    center_ceiling = depth_high - minimum_radius_z
    cell_size = map_config["cell_size_m"]
    interval_epsilon = min(0.01, map_config["depth_step_m"] / 1000)
    candidates: list[dict[str, Any]] = []

    for cell in cells:
        center_x = cell["x_m"] + cell_size / 2
        center_y = cell["y_m"] + cell_size / 2

        if control == "contact":
            for upper, lower in zip(cell["intervals"], cell["intervals"][1:]):
                upper_id = upper["rock_id"]
                lower_id = lower["rock_id"]
                host_is_upper = upper_id in host_ids and lower_id in contact_ids
                host_is_lower = lower_id in host_ids and upper_id in contact_ids
                if not host_is_upper and not host_is_lower:
                    continue
                contact_depth = float(upper["to_depth_m"])
                center_depth = (
                    contact_depth - interval_epsilon
                    if host_is_upper
                    else contact_depth + interval_epsilon
                )
                if center_floor <= center_depth <= center_ceiling:
                    candidates.append(
                        {
                            "x_m": center_x,
                            "y_m": center_y,
                            "depth_low": center_depth,
                            "depth_high": center_depth,
                            "center_host_rock_id": upper_id if host_is_upper else lower_id,
                            "contact_depth_m": contact_depth,
                            "contact_pair_rock_ids": [upper_id, lower_id],
                        }
                    )
            continue

        for interval in cell["intervals"]:
            if interval["rock_id"] not in host_ids:
                continue
            candidate_low = max(
                float(interval["from_depth_m"]) + interval_epsilon,
                center_floor,
            )
            candidate_high = min(
                float(interval["to_depth_m"]) - interval_epsilon,
                center_ceiling,
            )
            if candidate_low > candidate_high:
                continue
            base: dict[str, Any] = {
                "x_m": center_x,
                "y_m": center_y,
                "depth_low": candidate_low,
                "depth_high": candidate_high,
                "center_host_rock_id": interval["rock_id"],
            }
            if control == "fault":
                for fault in faults:
                    zone = _fault_zone_depth_range(
                        fault,
                        center_x,
                        center_y,
                        candidate_low,
                        candidate_high,
                    )
                    if zone is None:
                        continue
                    candidates.append(
                        {
                            **base,
                            "depth_low": zone[0],
                            "depth_high": zone[1],
                            "controlling_fault_id": fault["id"],
                        }
                    )
            else:
                candidates.append(base)
    return candidates


def _candidate_center_depth(
    candidate: dict[str, Any], seed: int, deposit_index: int, candidate_index: int
) -> float:
    low = float(candidate["depth_low"])
    high = float(candidate["depth_high"])
    if low == high:
        return round(low, 2)
    return round(
        _sample_range(
            seed,
            low,
            high,
            "deposit-center-z",
            deposit_index,
            candidate_index,
        ),
        2,
    )


def _center_conflicts(
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    deposits: list[dict[str, Any]],
) -> bool:
    x, y, z = center
    radius_x, radius_y, radius_z = radii
    for existing in deposits:
        other_x, other_y, other_z = existing["center_m"]
        other_radius_x, other_radius_y, other_radius_z = existing["radii_m"]
        inside_existing = (
            ((x - other_x) / other_radius_x) ** 2
            + ((y - other_y) / other_radius_y) ** 2
            + ((z - other_z) / other_radius_z) ** 2
            < 1
        )
        existing_inside_new = (
            ((other_x - x) / radius_x) ** 2
            + ((other_y - y) / radius_y) ** 2
            + ((other_z - z) / radius_z) ** 2
            < 1
        )
        if inside_existing or existing_inside_new:
            return True
    return False


def _rotated_horizontal_extents(
    radius_x: float,
    radius_y: float,
    rotation_deg: float,
) -> tuple[float, float]:
    """Return the axis-aligned half extents of a rotated horizontal ellipse."""
    angle = math.radians(rotation_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (
        math.sqrt((radius_x * cosine) ** 2 + (radius_y * sine) ** 2),
        math.sqrt((radius_x * sine) ** 2 + (radius_y * cosine) ** 2),
    )


def _fit_rotated_radii(
    desired_radius_x: float,
    desired_radius_y: float,
    minimum_radius_x: float,
    minimum_radius_y: float,
    rotation_deg: float,
    clearance_x: float,
    clearance_y: float,
) -> tuple[float, float] | None:
    """Shrink sampled radii, without crossing their minima, to fit the map."""

    def fits(radius_x: float, radius_y: float) -> bool:
        extent_x, extent_y = _rotated_horizontal_extents(
            radius_x, radius_y, rotation_deg
        )
        return extent_x <= clearance_x and extent_y <= clearance_y

    if not fits(minimum_radius_x, minimum_radius_y):
        return None
    if fits(desired_radius_x, desired_radius_y):
        return desired_radius_x, desired_radius_y

    low = 0.0
    high = 1.0
    for _ in range(32):
        fraction = (low + high) / 2
        radius_x = minimum_radius_x + fraction * (
            desired_radius_x - minimum_radius_x
        )
        radius_y = minimum_radius_y + fraction * (
            desired_radius_y - minimum_radius_y
        )
        if fits(radius_x, radius_y):
            low = fraction
        else:
            high = fraction

    radius_x = minimum_radius_x + low * (desired_radius_x - minimum_radius_x)
    radius_y = minimum_radius_y + low * (desired_radius_y - minimum_radius_y)
    # Round down so serialization cannot push a fitted body outside the map.
    return math.floor(radius_x * 100) / 100, math.floor(radius_y * 100) / 100


def _generate_deposits(
    config: dict[str, Any],
    seed: int,
    cells: list[dict[str, Any]],
    faults: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    map_config = config["map"]
    generation = config["deposit_generation"]
    count_low, count_high = (int(value) for value in generation["count"])
    width_m = map_config["width_cells"] * map_config["cell_size_m"]
    height_m = map_config["height_cells"] * map_config["cell_size_m"]
    candidate_sets: dict[str, list[dict[str, Any]]] = {}
    for definition in config["minerals"]:
        minimum_radius_x = float(definition["radius_x_m"][0])
        minimum_radius_y = float(definition["radius_y_m"][0])
        minimum_clearance = max(minimum_radius_x, minimum_radius_y)
        candidate_sets[definition["id"]] = [
            candidate
            for candidate in _definition_candidates(
                definition, cells, faults, map_config
            )
            if minimum_clearance
            <= float(candidate["x_m"])
            <= width_m - minimum_clearance
            and minimum_clearance
            <= float(candidate["y_m"])
            <= height_m - minimum_clearance
        ]
    eligible_types = [
        definition
        for definition in config["minerals"]
        if candidate_sets[definition["id"]]
    ]
    if len(eligible_types) < count_low:
        raise ValueError(
            "Сгенерированная геология поддерживает только "
            f"{len(eligible_types)} типов месторождений при минимуме {count_low}"
        )
    count = _sample_int(
        seed,
        count_low,
        min(count_high, len(eligible_types)),
        "deposit-count",
    )
    selected_types = _select_deposit_types(seed, eligible_types, count)
    deposits: list[dict[str, Any]] = []
    faults_by_id = {fault["id"]: fault for fault in faults}

    for index, definition in enumerate(selected_types):
        depth_low, depth_high = definition["allowed_depth_m"]
        minimum_radius_x = float(definition["radius_x_m"][0])
        minimum_radius_y = float(definition["radius_y_m"][0])
        default_rotation = _sample_range(seed, 0, 180, "deposit-rotation", index)
        radius_x = round(
            min(
                width_m / 2,
                _sample_range(seed, *definition["radius_x_m"], "deposit-radius", index, "x"),
            ),
            2,
        )
        radius_y = round(
            min(
                height_m / 2,
                _sample_range(seed, *definition["radius_y_m"], "deposit-radius", index, "y"),
            ),
            2,
        )
        minimum_radius_z, configured_radius_z_high = definition["radius_z_m"]
        candidates = candidate_sets[definition["id"]]
        start = _sample_int(
            seed, 0, len(candidates) - 1, "deposit-candidate", definition["id"], index
        )
        selected_candidate: dict[str, Any] | None = None
        selected_center_z = 0.0
        selected_radius_x = 0.0
        selected_radius_y = 0.0
        selected_radius_z = 0.0
        selected_rotation = 0.0
        fallback_choice: tuple[
            dict[str, Any], float, float, float, float, float
        ] | None = None

        for offset in range(len(candidates)):
            candidate_index = (start + offset) % len(candidates)
            candidate = candidates[candidate_index]
            candidate_fault = faults_by_id.get(candidate.get("controlling_fault_id"))
            candidate_rotation = round(
                float(candidate_fault["strike_deg"])
                if candidate_fault is not None
                else default_rotation,
                2,
            )
            fitted_radii = _fit_rotated_radii(
                radius_x,
                radius_y,
                minimum_radius_x,
                minimum_radius_y,
                candidate_rotation,
                min(float(candidate["x_m"]), width_m - float(candidate["x_m"])),
                min(float(candidate["y_m"]), height_m - float(candidate["y_m"])),
            )
            if fitted_radii is None:
                continue
            candidate_radius_x, candidate_radius_y = fitted_radii
            center_z = _candidate_center_depth(candidate, seed, index, candidate_index)
            maximum_radius_z = min(
                float(configured_radius_z_high),
                center_z - depth_low,
                depth_high - center_z,
            )
            if maximum_radius_z < minimum_radius_z:
                continue
            radius_z = round(
                _sample_range(
                    seed,
                    float(minimum_radius_z),
                    maximum_radius_z,
                    "deposit-radius",
                    index,
                    "z",
                    candidate_index,
                ),
                2,
            )
            center = (candidate["x_m"], candidate["y_m"], center_z)
            choice = (
                candidate,
                center_z,
                candidate_radius_x,
                candidate_radius_y,
                radius_z,
                candidate_rotation,
            )
            if fallback_choice is None:
                fallback_choice = choice
            if not _center_conflicts(
                center,
                (candidate_radius_x, candidate_radius_y, radius_z),
                deposits,
            ):
                selected_candidate = candidate
                selected_center_z = center_z
                selected_radius_x = candidate_radius_x
                selected_radius_y = candidate_radius_y
                selected_radius_z = radius_z
                selected_rotation = candidate_rotation
                break

        if selected_candidate is None:
            if fallback_choice is None:
                raise ValueError(
                    f"Не удалось разместить месторождение {definition['id']} "
                    "в допустимой геологической позиции"
                )
            (
                selected_candidate,
                selected_center_z,
                selected_radius_x,
                selected_radius_y,
                selected_radius_z,
                selected_rotation,
            ) = fallback_choice

        model = deepcopy(definition["geological_model"])
        control = model["control"]
        body_rock_id = model.get("body_rock_id")
        center_host_rock_id = (
            body_rock_id if control == "intrusive" else selected_candidate["center_host_rock_id"]
        )
        deposit_number = index + 1
        controlling_fault = faults_by_id.get(
            selected_candidate.get("controlling_fault_id")
        )
        shape = {
            "geometry": model.get("geometry", "irregular_ellipsoid"),
            "rotation_deg": round(selected_rotation, 2),
            "irregularity": round(
                _sample_range(
                    seed,
                    *generation["shape_irregularity"],
                    "deposit-irregularity",
                    index,
                ),
                3,
            ),
            "vertical_irregularity": round(
                _sample_range(
                    seed,
                    *generation["vertical_irregularity"],
                    "deposit-vertical-irregularity",
                    index,
                ),
                3,
            ),
            "noise_scale_cells": round(
                _sample_range(
                    seed,
                    *generation["noise_scale_cells"],
                    "deposit-noise-scale",
                    index,
                ),
                3,
            ),
            "concentration_variation": round(
                _sample_range(
                    seed,
                    *generation["concentration_variation"],
                    "deposit-concentration-variation",
                    index,
                ),
                3,
            ),
        }
        if controlling_fault is not None:
            shape["dip_deg"] = controlling_fault["dip_deg"]
        grade = definition["grade"]
        deposits.append(
            {
                "id": f"{definition['id']}_deposit_{deposit_number}",
                "mineral_id": definition["id"],
                "name": f"{definition['name']} №{deposit_number}",
                "mineral": definition["mineral"],
                "color": definition["color"],
                "allowed_depth_m": definition["allowed_depth_m"],
                "center_m": [
                    selected_candidate["x_m"],
                    selected_candidate["y_m"],
                    selected_center_z,
                ],
                "radii_m": [selected_radius_x, selected_radius_y, selected_radius_z],
                "shape": shape,
                "geological_model": model,
                "permitted_host_rock_ids": list(model["host_rock_ids"]),
                "permitted_mineralized_rock_ids": (
                    [body_rock_id]
                    if control == "intrusive"
                    else list(model["host_rock_ids"])
                ),
                "center_host_rock_id": center_host_rock_id,
                "country_host_rock_id": (
                    selected_candidate["center_host_rock_id"]
                    if control == "intrusive"
                    else None
                ),
                "controlling_fault_id": selected_candidate.get("controlling_fault_id"),
                "contact_depth_m": selected_candidate.get("contact_depth_m"),
                "contact_pair_rock_ids": selected_candidate.get("contact_pair_rock_ids"),
                "max_grade": round(
                    _sample_range(
                        seed,
                        *grade["maximum"],
                        "deposit-grade",
                        index,
                    ),
                    4,
                ),
                "grade_unit": grade["unit"],
                "display_threshold": grade["display_threshold"],
                "origin": "generated",
            }
        )
    return deposits


def _deposit_slice_for_cell(
    map_config: dict[str, Any],
    deposit: dict[str, Any],
    x_index: int,
    y_index: int,
    seed: int,
) -> dict[str, float] | None:
    cell_size = map_config["cell_size_m"]
    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    x = (x_index + 0.5) * cell_size
    y = (y_index + 0.5) * cell_size
    center_x, center_y, center_z = deposit["center_m"]
    radius_x, radius_y, radius_z = deposit["radii_m"]
    shape = deposit["shape"]
    angle = math.radians(shape["rotation_deg"])
    delta_x = x - center_x
    delta_y = y - center_y
    rotated_x = delta_x * math.cos(angle) + delta_y * math.sin(angle)
    rotated_y = -delta_x * math.sin(angle) + delta_y * math.cos(angle)
    boundary_noise = _fractal_noise_2d(
        seed,
        x_index,
        y_index,
        shape["noise_scale_cells"],
        deposit["id"],
        "boundary",
    )
    boundary_scale = 1 - shape["irregularity"] * (1 - boundary_noise)
    horizontal_distance = (
        (rotated_x / (radius_x * boundary_scale)) ** 2
        + (rotated_y / (radius_y * boundary_scale)) ** 2
    )
    if horizontal_distance >= 1:
        return None

    half_height = radius_z * math.sqrt(1 - horizontal_distance)
    top_noise = _fractal_noise_2d(
        seed,
        x_index,
        y_index,
        shape["noise_scale_cells"],
        deposit["id"],
        "top",
    )
    bottom_noise = _fractal_noise_2d(
        seed,
        x_index,
        y_index,
        shape["noise_scale_cells"],
        deposit["id"],
        "bottom",
    )
    top_factor = 1 - shape["vertical_irregularity"] * (1 - top_noise)
    bottom_factor = 1 - shape["vertical_irregularity"] * (1 - bottom_noise)
    top = max(0.0, center_z - half_height * top_factor)
    bottom = min(float(total_depth), center_z + half_height * bottom_factor)
    if bottom <= top:
        return None

    grade_noise = _fractal_noise_2d(
        seed,
        x_index,
        y_index,
        shape["noise_scale_cells"],
        deposit["id"],
        "grade",
    )
    grade_factor = 1 - shape["concentration_variation"] * (1 - grade_noise)
    maximum_grade = deposit["max_grade"] * (1 - horizontal_distance) * grade_factor
    return {
        "top": top,
        "bottom": bottom,
        "maximum_grade": maximum_grade,
    }


def _replace_with_intrusive_rock(
    intervals: list[dict[str, Any]],
    top: float,
    bottom: float,
    rock: dict[str, Any],
    deposit: dict[str, Any],
    x_index: int,
    y_index: int,
    seed: int,
) -> list[dict[str, Any]]:
    top = round(top, 2)
    bottom = round(bottom, 2)
    if top >= bottom:
        return intervals

    country_rock_ids = sorted(
        {
            interval["rock_id"]
            for interval in intervals
            if max(top, interval["from_depth_m"]) < min(bottom, interval["to_depth_m"])
        }
    )
    if not country_rock_ids:
        return intervals

    result: list[dict[str, Any]] = []
    for interval in intervals:
        interval_top = float(interval["from_depth_m"])
        interval_bottom = float(interval["to_depth_m"])
        if interval_bottom <= top or interval_top >= bottom:
            result.append(interval)
            continue
        if interval_top < top:
            left = deepcopy(interval)
            left["to_depth_m"] = top
            result.append(left)
        if interval_bottom > bottom:
            right = deepcopy(interval)
            right["from_depth_m"] = bottom
            result.append(right)

    density_low, density_high = rock["density_g_cm3"]
    porosity_low, porosity_high = rock["porosity_percent"]
    result.append(
        {
            "from_depth_m": top,
            "to_depth_m": bottom,
            "rock_id": rock["id"],
            "properties": {
                "density_g_cm3": round(
                    _sample_range(
                        seed,
                        density_low,
                        density_high,
                        "intrusive-density",
                        deposit["id"],
                        x_index,
                        y_index,
                    ),
                    3,
                ),
                "porosity_percent": round(
                    _sample_range(
                        seed,
                        porosity_low,
                        porosity_high,
                        "intrusive-porosity",
                        deposit["id"],
                        x_index,
                        y_index,
                    ),
                    3,
                ),
            },
            "country_rock_ids": country_rock_ids,
            "intrusive_deposit_id": deposit["id"],
            "origin": "generated_intrusion",
        }
    )
    return sorted(result, key=lambda item: item["from_depth_m"])


def _clip_to_rocks(
    intervals: list[dict[str, Any]],
    top: float,
    bottom: float,
    rock_ids: set[str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for interval in intervals:
        if interval["rock_id"] not in rock_ids:
            continue
        overlap_top = max(top, float(interval["from_depth_m"]))
        overlap_bottom = min(bottom, float(interval["to_depth_m"]))
        if overlap_top < overlap_bottom:
            result.append(
                {
                    "top": overlap_top,
                    "bottom": overlap_bottom,
                    "rock_id": interval["rock_id"],
                    "country_rock_ids": interval.get("country_rock_ids"),
                }
            )
    return result


def _matching_contact_depths(
    intervals: list[dict[str, Any]],
    host_ids: set[str],
    contact_ids: set[str],
) -> list[float]:
    result: list[float] = []
    for upper, lower in zip(intervals, intervals[1:]):
        if (
            upper["rock_id"] in host_ids
            and lower["rock_id"] in contact_ids
        ) or (
            lower["rock_id"] in host_ids
            and upper["rock_id"] in contact_ids
        ):
            result.append(float(upper["to_depth_m"]))
    return result


def _mineralization_for_deposit_cell(
    cell: dict[str, Any],
    deposit: dict[str, Any],
    faults_by_id: dict[str, dict[str, Any]],
    map_config: dict[str, Any],
    seed: int,
) -> list[dict[str, Any]]:
    raw = _deposit_slice_for_cell(
        map_config, deposit, cell["x_index"], cell["y_index"], seed
    )
    if raw is None or raw["maximum_grade"] < deposit["display_threshold"]:
        return []

    model = deposit["geological_model"]
    control = model["control"]
    top = raw["top"]
    bottom = raw["bottom"]
    if control == "contact":
        contacts = _matching_contact_depths(
            cell["intervals"],
            set(model["host_rock_ids"]),
            set(model["contact_rock_ids"]),
        )
        if not contacts:
            return []
        contact_depth = min(contacts, key=lambda value: abs(value - deposit["center_m"][2]))
        buffer_m = float(model["contact_buffer_m"])
        top = max(top, contact_depth - buffer_m)
        bottom = min(bottom, contact_depth + buffer_m)
    elif control == "fault":
        fault = faults_by_id.get(deposit["controlling_fault_id"])
        if fault is None:
            return []
        cell_size = map_config["cell_size_m"]
        x_m = cell["x_m"] + cell_size / 2
        y_m = cell["y_m"] + cell_size / 2
        zone = _fault_zone_depth_range(fault, x_m, y_m, top, bottom)
        if zone is None:
            return []
        top, bottom = zone

    mineralized_rock_ids = (
        {model["body_rock_id"]}
        if control == "intrusive"
        else set(model["host_rock_ids"])
    )
    segments = _clip_to_rocks(cell["intervals"], top, bottom, mineralized_rock_ids)
    maximum_grade = raw["maximum_grade"]
    average_grade = max(deposit["display_threshold"], maximum_grade * 0.62)
    result: list[dict[str, Any]] = []
    for segment in segments:
        rounded_top = round(segment["top"], 2)
        rounded_bottom = round(segment["bottom"], 2)
        if rounded_top >= rounded_bottom:
            continue
        item = {
            "deposit_id": deposit["id"],
            "mineral": deposit["mineral"],
            "host_rock_id": segment["rock_id"],
            "geological_control": control,
            "from_depth_m": rounded_top,
            "to_depth_m": rounded_bottom,
            "average_grade": round(average_grade, 4),
            "maximum_grade": round(maximum_grade, 4),
            "grade_unit": deposit["grade_unit"],
        }
        if segment["country_rock_ids"]:
            item["country_rock_ids"] = segment["country_rock_ids"]
        result.append(item)
    return result


def _apply_deposits(
    cells: list[dict[str, Any]],
    deposits: list[dict[str, Any]],
    faults: list[dict[str, Any]],
    rocks: list[dict[str, Any]],
    map_config: dict[str, Any],
    seed: int,
) -> None:
    rocks_by_id = {rock["id"]: rock for rock in rocks}
    faults_by_id = {fault["id"]: fault for fault in faults}

    for deposit in deposits:
        model = deposit["geological_model"]
        if model["control"] != "intrusive":
            continue
        body_rock = rocks_by_id[model["body_rock_id"]]
        for cell in cells:
            raw = _deposit_slice_for_cell(
                map_config, deposit, cell["x_index"], cell["y_index"], seed
            )
            if raw is None:
                continue
            cell["intervals"] = _replace_with_intrusive_rock(
                cell["intervals"],
                raw["top"],
                raw["bottom"],
                body_rock,
                deposit,
                cell["x_index"],
                cell["y_index"],
                seed,
            )

    for cell in cells:
        cell["mineralization"] = []
        for deposit in deposits:
            cell["mineralization"].extend(
                _mineralization_for_deposit_cell(
                    cell, deposit, faults_by_id, map_config, seed
                )
            )


def generate_map(config: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """Generate a complete synthetic ground-truth map in interval form."""
    _validate_config(config)
    config = deepcopy(config)
    map_config = config["map"]
    effective_seed = secrets.randbits(63) if seed is None else int(seed)
    map_config["seed"] = effective_seed
    layers = _generate_layers(config, effective_seed)
    faults = _generate_faults(map_config, config["geology"], effective_seed)

    cells: list[dict[str, Any]] = []
    for y_index in range(map_config["height_cells"]):
        for x_index in range(map_config["width_cells"]):
            boundaries = _layer_boundaries(
                map_config,
                config["geology"],
                layers,
                faults,
                x_index,
                y_index,
                effective_seed,
            )
            intervals = _make_intervals(
                config["rocks"], layers, boundaries, x_index, y_index, effective_seed
            )
            cells.append(
                {
                    "x_index": x_index,
                    "y_index": y_index,
                    "x_m": x_index * map_config["cell_size_m"],
                    "y_m": y_index * map_config["cell_size_m"],
                    "surface_elevation_m": 0,
                    "intervals": intervals,
                    "mineralization": [],
                }
            )

    deposits = _generate_deposits(config, effective_seed, cells, faults)
    _apply_deposits(
        cells,
        deposits,
        faults,
        config["rocks"],
        map_config,
        effective_seed,
    )
    rock_interval_counts = {rock["id"]: 0 for rock in config["rocks"]}
    for cell in cells:
        cell["mineralization"].sort(
            key=lambda item: (item["from_depth_m"], item["deposit_id"])
        )
        for interval in cell["intervals"]:
            rock_interval_counts[interval["rock_id"]] += 1
    mineralized_cells = sum(bool(cell["mineralization"]) for cell in cells)

    total_depth = map_config["depth_cells"] * map_config["depth_step_m"]
    return {
        "schema_version": "2.0",
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
        "faults": faults,
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
