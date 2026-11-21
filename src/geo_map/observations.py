"""Vertical and inclined drilling campaigns sampled from the ground-truth model."""

from __future__ import annotations

import csv
import json
import math
import secrets
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from .boreholes import collar_bounds, orientation, validate_trajectory
from .drilling_plan import DEFAULT_RANDOM_FRACTION, target_boreholes
from .geophysical_observations import GEOPHYSICAL_DIRECTORIES, GEOPHYSICAL_TABLES, LEGACY_GEOPHYSICAL_TABLE, split_legacy_geophysical_bundle
from .observation_tools import TruthSampler, _number, _rng, measure_grade
from .observation_models import EXTRA_TABLE_FIELDS, extend_campaign, survey_preliminary, validate_extensions
from .observation_objects import save_observation_objects
from .observation_sources import BOREHOLE_SOURCE_TABLES, describe_borehole_sources, make_borehole_source


TABLE_FIELDS = {
    "borehole_collars": "campaign_id hole_id x_m y_m collar_elevation_m total_depth_m azimuth_deg dip_deg coordinate_system position_uncertainty_m drilling_method start_date end_date hole_status".split(),
    "borehole_lithology": "campaign_id hole_id interval_id from_m to_m observed_rock_id observed_rock_name description weathering alteration confidence observer logged_date".split(),
    "borehole_assays": "campaign_id sample_id hole_id from_m to_m analyte result_value result_qualifier unit detection_limit analysis_method laboratory certificate_id qc_type qc_flag".split(),
    "downhole_properties": "campaign_id hole_id measurement_id from_m to_m depth_m density_g_cm3 porosity_percent measurement_method density_error_g_cm3 porosity_error_percent qc_flag".split(),
    "structural_observations": "campaign_id observation_id hole_id x_m y_m depth_m feature_type strike_deg dip_deg dip_direction_deg offset_estimate_m confidence observation_method notes".split(),
}
TABLE_FIELDS.update(EXTRA_TABLE_FIELDS)

SUMMARY_FOLDERS = {
    **dict.fromkeys(BOREHOLE_SOURCE_TABLES, "boreholes"),
    **dict.fromkeys(("trenches", "trench_intervals", "trench_samples", "trench_paths"), "trenches"),
    "surface_geochemistry": "surface_geochemistry",
    "outcrop_observations": "outcrops",
    "terrain_observations": "terrain",
    **GEOPHYSICAL_DIRECTORIES,
    "quality_control": "quality_control",
}


def load_observation_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _validate_config(config: dict[str, Any], dimensions: dict[str, Any]) -> None:
    for key in ("campaign_id", "title", "date"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"Не заполнено поле экспедиции {key}")
    date.fromisoformat(config["date"])
    if not isinstance(config.get("ideal", False), bool):
        raise ValueError("ideal должен быть логическим значением")
    drilling = config["drilling"]
    depth = _number(drilling["depth_m"], "drilling.depth_m", positive=True)
    sample_length = _number(drilling["sample_length_m"], "drilling.sample_length_m", positive=True)
    if sample_length < 0.000001:
        raise ValueError("Шаг опробования должен быть не меньше 0.000001 м")
    layout = drilling.get("layout", "grid")
    if layout not in {"grid", "random", "manual", "hybrid"}:
        raise ValueError("drilling.layout: допустимы grid, random, manual, hybrid")
    if layout == "hybrid":
        random_fraction = _number(drilling.get("random_fraction", DEFAULT_RANDOM_FRACTION),
                                  "drilling.random_fraction", positive=True)
        if random_fraction >= 1:
            raise ValueError("drilling.random_fraction должна быть меньше 1")
    if layout == "manual":
        holes = drilling.get("holes", [])
        if not holes:
            raise ValueError("Для ручного плана нужны drilling.holes")
        ids = set()
        for hole in holes:
            hole_id = hole.get("hole_id")
            if not isinstance(hole_id, str) or not hole_id.strip() or hole_id in ids:
                raise ValueError("hole_id должен быть непустым и уникальным")
            ids.add(hole_id)
            for axis, limit in (("x_m", "width_m"), ("y_m", "height_m")):
                if _number(hole[axis], axis) >= dimensions[limit]:
                    raise ValueError(f"{hole_id}: устье скважины выходит за границы карты")
            _number(hole.get("depth_m", depth), "depth_m", positive=True)
    else:
        count = drilling["hole_count"]
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10000:
            raise ValueError("drilling.hole_count: требуется целое число от 1 до 10000")
    holes = _plan_holes(dimensions, drilling, seed=0)
    planned_samples = sum(math.ceil(hole["depth_m"] / sample_length) for hole in holes)
    noise = config.get("noise", {})
    for key in ("position_sigma_m", "boundary_sigma_m", "density_sigma_g_cm3", "porosity_sigma_percent", "assay_relative_sigma", "assay_detection_limit_sigma_fraction"):
        _number(noise.get(key, 0), f"noise.{key}")
    for key in ("missing_sample_probability", "lithology_error_probability"):
        if _number(noise.get(key, 0), f"noise.{key}") > 1:
            raise ValueError(f"noise.{key}: вероятность должна лежать в [0, 1]")
    analytes = config.get("analytes", [])
    names = [item.get("analyte") for item in analytes]
    if not names or any(not isinstance(name, str) or not name.strip() for name in names) or len(names) != len(set(names)):
        raise ValueError("Нужен непустой список уникальных аналитов")
    for item in analytes:
        if not isinstance(item.get("unit"), str) or not item["unit"].strip():
            raise ValueError("Для каждого аналита нужна единица измерения")
        _number(item["detection_limit"], "detection_limit", positive=True)
    if planned_samples * len(analytes) > 1000000:
        raise ValueError("План превышает миллион анализов; увеличьте шаг проб или уменьшите число скважин")
    validate_extensions(config, dimensions, planned_samples, planned_samples * len(analytes))


def _plan_holes(dimensions: dict[str, Any], drilling: dict[str, Any], seed: int, *,
                geophysical_channels: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    defaults = orientation(drilling)
    layout = drilling.get("layout", "grid")
    if layout == "manual":
        holes = []
        for settings in drilling["holes"]:
            hole = {"depth_m": drilling["depth_m"], **settings,
                    **orientation({**defaults, **settings})}
            validate_trajectory(hole, dimensions)
            holes.append(hole)
        return holes
    patterns = drilling.get("orientations", [defaults])
    if not isinstance(patterns, list) or not patterns or any(not isinstance(item, dict) for item in patterns):
        raise ValueError("drilling.orientations: нужен непустой список направлений")
    angles = [orientation({**defaults, **item}) for item in patterns]
    bounds = [collar_bounds(dimensions, drilling["depth_m"], item) for item in angles]
    count = drilling["hole_count"]
    width, height = dimensions["width_m"], dimensions["height_m"]
    columns = max(1, min(count, math.ceil(math.sqrt(count * width / height))))
    rows = math.ceil(count / columns)
    holes = []
    for index in range(count):
        rng = _rng(seed, "plan", index)
        (xmin, xmax), (ymin, ymax) = bounds[index % len(bounds)]
        if layout in {"random", "hybrid"}:
            fx, fy = rng.uniform(0.05, 0.95), rng.uniform(0.05, 0.95)
        else:
            fx = ((index % columns) + 0.5) / columns
            fy = ((index // columns) + 0.5) / rows
        holes.append({"hole_id": f"BH-{index + 1:03d}", "x_m": xmin + fx * (xmax - xmin),
                      "y_m": ymin + fy * (ymax - ymin), "depth_m": drilling["depth_m"], **angles[index % len(angles)]})
    if layout == "hybrid" and geophysical_channels:
        target_boreholes(holes, bounds, dimensions, geophysical_channels,
                         drilling.get("random_fraction", DEFAULT_RANDOM_FRACTION))
    return holes


def generate_observations(truth_map: dict[str, Any], config: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """Return measured data only; latent sample values never leave this function."""
    config = deepcopy(config)
    dimensions = truth_map["dimensions"]
    _validate_config(config, dimensions)
    seed = secrets.randbits(63) if seed is None else int(seed)
    ideal = config.get("ideal", False)
    noise = {} if ideal else config.get("noise", {})
    sigma = lambda key: noise.get(key, 0.0)
    sampler = TruthSampler(truth_map)
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in TABLE_FIELDS}
    rocks = {rock["id"]: rock for rock in truth_map["rocks"]}
    campaign_id, logged_date = config["campaign_id"], config["date"]
    sample_count = planned_samples = 0
    source_samples: dict[str, dict[str, Any]] = {}
    structures = config.get("structures")
    observe_contacts = structures is None or (structures.get("enabled", False) and structures.get("observe_contacts", True))

    def append(table: str, **values: Any) -> None:
        row = dict.fromkeys(TABLE_FIELDS[table])
        row["campaign_id"] = campaign_id
        if not values.keys() <= row.keys():
            raise ValueError("Неизвестное поле наблюдения")
        row.update(values)
        tables[table].append(row)

    survey_preliminary(truth_map, config, seed, sampler, append)
    drilling = config["drilling"]
    geophysical_channels = {method: tables[table] for method, table in GEOPHYSICAL_TABLES.items()}
    holes = _plan_holes(dimensions, drilling, seed, geophysical_channels=geophysical_channels)
    step = drilling["sample_length_m"]
    for hole in holes:
        hole_id, x, y, depth = hole["hole_id"], hole["x_m"], hole["y_m"], hole["depth_m"]
        hole["collar_elevation_m"] = sampler.column(x, y).get("surface_elevation_m", 0)
        rng = _rng(seed, "collar", hole_id)
        append("borehole_collars", hole_id=hole_id,
               x_m=round(x + rng.gauss(0, sigma("position_sigma_m")), 6),
               y_m=round(y + rng.gauss(0, sigma("position_sigma_m")), 6),
               collar_elevation_m=hole["collar_elevation_m"], total_depth_m=depth, azimuth_deg=hole["azimuth_deg"], dip_deg=hole["dip_deg"],
               coordinate_system="local_cartesian", position_uncertainty_m=sigma("position_sigma_m"),
               drilling_method="synthetic_core", start_date=logged_date, end_date=logged_date, hole_status="completed")
        lithology = []
        for part in sampler.borehole_segments(hole, 0, depth):
            if lithology and lithology[-1]["rock_id"] == part["rock_id"]:
                lithology[-1]["to_m"] = part["to_m"]
            else:
                lithology.append({"from_m": part["from_m"], "to_m": part["to_m"], "rock_id": part["rock_id"]})
        boundaries = [0.0]
        for index, interval in enumerate(lithology[:-1]):
            boundary = interval["to_m"]
            next_end = lithology[index + 1]["to_m"]
            limit = 0.49 * min(boundary - interval["from_m"], next_end - boundary)
            shift = _rng(seed, "boundary", hole_id, index).gauss(0, sigma("boundary_sigma_m"))
            boundaries.append(boundary + max(-limit, min(limit, shift)))
        boundaries.append(depth)
        for index, interval in enumerate(lithology):
            rock = rocks[interval["rock_id"]]
            rng = _rng(seed, "lithology", hole_id, index)
            candidates = [item for item in rocks.values() if item["category"] == rock["category"] and item["id"] != rock["id"]]
            if candidates and rng.random() < sigma("lithology_error_probability"):
                rock = rng.choice(candidates)
            append("borehole_lithology", hole_id=hole_id, interval_id=f"{hole_id}-L{index + 1:03d}",
                   from_m=boundaries[index], to_m=boundaries[index + 1], observed_rock_id=rock["id"],
                   observed_rock_name=rock["name"], description=f"Керновое описание: {rock['name']}",
                   confidence="high" if ideal else "medium", observer="synthetic_geologist", logged_date=logged_date)
            if index and observe_contacts:
                append("structural_observations", hole_id=hole_id, observation_id=f"{hole_id}-C{index:03d}",
                       depth_m=boundaries[index], feature_type="contact", confidence="high" if ideal else "medium",
                       observation_method="core_logging", notes="Контакт пород в керне; ориентация не определялась")

        for index in range(math.ceil(depth / step)):
            start = round(index * step, 6)
            # Decimal steps can make ceil(depth / step) one interval too large.
            if start >= depth:
                break
            end = min(depth, round((index + 1) * step, 6))
            if start >= end:
                raise ValueError("Шаг опробования меньше поддерживаемой точности 0.000001 м")
            sample_id = f"{hole_id}-S{index + 1:04d}"
            planned_samples += 1
            rng = _rng(seed, "sample", sample_id)
            if rng.random() < sigma("missing_sample_probability"):
                continue
            sample_count += 1
            sample = sampler.sample_borehole(hole, start, end, config["analytes"])
            source_samples[sample_id] = {"source": "borehole", "hole_id": hole_id,
                                         "grades": sample["grades"], "analytes": config["analytes"]}
            append("downhole_properties", hole_id=hole_id, measurement_id=f"{hole_id}-P{index + 1:04d}",
                   from_m=start, to_m=end,
                   density_g_cm3=round(max(0.000001, sample["density_g_cm3"] + rng.gauss(0, sigma("density_sigma_g_cm3"))), 6),
                   porosity_percent=round(max(0, min(100, sample["porosity_percent"] + rng.gauss(0, sigma("porosity_sigma_percent")))), 6),
                   measurement_method="synthetic_core_measurement", density_error_g_cm3=sigma("density_sigma_g_cm3"),
                   porosity_error_percent=sigma("porosity_sigma_percent"), qc_flag="not_checked")
            for analyte in config["analytes"]:
                qc = config.get("quality_control", {})
                result = measure_grade(sample["grades"][analyte["analyte"]], analyte, noise, seed, sample_id,
                                       ideal=ideal, bias_fraction=qc.get("batch_bias_fraction", 0),
                                       contamination_limits=qc.get("contamination_detection_limits", 0))
                append("borehole_assays", sample_id=sample_id, hole_id=hole_id, from_m=start, to_m=end,
                       analyte=analyte["analyte"], **result,
                       analysis_method="synthetic_assay", laboratory="SYNTHETIC-LAB", certificate_id=f"{campaign_id}-CERT",
                       qc_type="primary", qc_flag="not_checked")

    extra = extend_campaign(truth_map, config, seed, holes, source_samples, tables, append)
    observed_ids = {item["observed_rock_id"] for name in ("borehole_lithology", "trench_intervals", "outcrop_observations") for item in tables[name]}
    bundle = {
        "schema_version": "1.7", "data_kind": "exploration_observations",
        "campaign": {"campaign_id": campaign_id, "title": config["title"], "date": logged_date,
                     "coordinate_system": "local_cartesian", "width_m": dimensions["width_m"], "height_m": dimensions["height_m"]},
        "plan": {"layout": config["drilling"].get("layout", "grid"), "sample_length_m": step,
                 "borehole_path": "straight", "borehole_depth_reference": "measured_depth_m",
                 "ideal": ideal, "analytes": [{key: item[key] for key in ("analyte", "unit", "detection_limit")} for item in config["analytes"]], "methods": extra["methods"]},
        "summary": {"hole_count": len(holes), "drilled_m": round(sum(hole["depth_m"] for hole in holes), 6),
                    "vertical_hole_count": sum(hole["dip_deg"] == -90 for hole in holes),
                    "inclined_hole_count": sum(hole["dip_deg"] != -90 for hole in holes),
                    "sample_count": sample_count, "missing_sample_count": planned_samples - sample_count,
                    "assay_count": len(tables["borehole_assays"]), "lithology_count": len(tables["borehole_lithology"]),
                    "property_count": len(tables["downhole_properties"]),
                    "contact_count": sum(row["feature_type"] == "contact" for row in tables["structural_observations"]),
                    "total_missing_sample_count": planned_samples - sample_count + extra["summary"]["trench_missing_sample_count"] + extra["summary"]["surface_unavailable_count"],
                    **extra["summary"]},
        "rock_catalog": [{"id": rock["id"], "name": rock["name"], "color": rock["color"]} for rock in rocks.values() if rock["id"] in observed_ids],
        "notes": [
            "Моделируются прямолинейные вертикальные и наклонные скважины, описание керна, интервальные анализы, физические свойства и включённые дополнительные методы.",
            "Скважинные total_depth_m, from_m, to_m и depth_m — расстояния вдоль ствола от устья. Азимут отсчитывается от +Y по часовой стрелке к +X; dip_deg — угол от горизонтали вниз, -90° означает вертикаль. Вертикальная глубина равна расстоянию вдоль ствола × sin(|dip_deg|).",
            "Отметка устья и отметки обнажений заданы относительно общего нулевого уровня. Глубины почвенных и траншейных проб отсчитываются от местной поверхности.",
            "В скважинных и траншейных пробах содержание постоянно внутри сохранённого интервала минерализации; вне таких интервалов принято нулевым. Для почвенной геохимии используется отдельная условная модель фона и переноса.",
            "Шаг опробования не повышает пространственное разрешение исходной модели.",
            "Результат с квалификатором lt означает содержание ниже указанного предела обнаружения, а не измеренный ноль.",
            "Ориентация разлома записывается только при ориентированном керне; ориентация контактов и смещение не определяются.",
            "Фон и перенос поверхностной геохимии — условная синтетическая модель. Алмазы, уголь и составные показатели для почв не поддерживаются.",
            "Траншейная проба представляет полосу у дна вдоль оси выработки; ширина траншеи не добавляет поперечного разрешения. При мощной почве коренные породы не вскрываются.",
            "QA/QC оценивается по измеренным дубликатам, холостым пробам и сертифицированным значениям стандартов. Проверка отдельных первичных проб остаётся not_checked.",
        ],
        "table_fields": deepcopy(TABLE_FIELDS),
        "tables": tables,
        "geojson": extra["geojson"],
    }
    if drilling.get("layout") == "hybrid":
        bundle["plan"]["random_fraction"] = drilling.get("random_fraction", DEFAULT_RANDOM_FRACTION)
        bundle["drilling_targets"] = {hole["hole_id"]: hole["target"] for hole in holes if "target" in hole}
    bundle["borehole_sources"] = describe_borehole_sources(bundle)
    return bundle


def _save_bundle(bundle: dict[str, Any], directory: str | Path, *, group_tables: bool = False) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    def export_path(name: str, extension: str) -> Path:
        folder = directory
        if group_tables:
            folder = directory / "tables" / SUMMARY_FOLDERS[name]
            folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{name}.{extension}"

    output = directory / "observations.json"
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for name, fields in bundle["table_fields"].items():
        with export_path(name, "csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(bundle["tables"][name])
    for name, data in bundle.get("geojson", {}).items():
        export_path(name, "geojson").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return output


def save_observations(bundle: dict[str, Any], directory: str | Path) -> Path:
    """Export the campaign, drilling sources and individual observation objects."""
    bundle = split_legacy_geophysical_bundle(bundle)
    output = _save_bundle(bundle, directory, group_tables=True)
    sources = describe_borehole_sources(bundle)
    (Path(directory) / "borehole_sources.json").write_text(
        json.dumps({"schema_version": bundle["schema_version"], "data_kind": "borehole_source_manifest",
                    "campaign": bundle["campaign"], "borehole_sources": sources},
                   ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for source in sources:
        _save_bundle(make_borehole_source(bundle, source["kind"]), Path(directory) / source["directory"])
    save_observation_objects(bundle, output.parent)
    # Clear generated files left at the root by earlier versions after their replacements exist.
    for names, extension in ((bundle["table_fields"], "csv"), (bundle.get("geojson", {}), "geojson")):
        for name in names:
            old_file = output.parent / f"{name}.{extension}"
            if old_file.is_file():
                old_file.unlink()
    if set(GEOPHYSICAL_TABLES.values()) <= bundle["table_fields"].keys():
        for folder in (output.parent, output.parent / "tables/geophysics"):
            for extension in ("csv", "geojson"):
                (folder / f"{LEGACY_GEOPHYSICAL_TABLE}.{extension}").unlink(missing_ok=True)
    return output
