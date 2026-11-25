from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from geo_map import (
    build_viewer, generate_map, generate_observations, load_config,
    load_observation_config, save_map, save_observations,
)
from geo_map.recognition import recognize_deposits, save_recognition
from geo_map.geophysics import add_geophysical_fields


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генерация синтетической геологической карты"
    )
    parser.add_argument(
        "--map",
        type=Path,
        default=None,
        help="Использовать существующий map.json для новой экспедиции",
    )
    parser.add_argument(
        "--recompute-geophysics",
        action="store_true",
        help="Пересчитать геофизические поля сохранённой карты по текущим справочникам",
    )
    parser.add_argument(
        "--observations-config",
        type=Path,
        default=PROJECT_ROOT / "config/observations.json",
        help="JSON-файл с планом экспедиции и погрешностями наблюдений",
    )
    parser.add_argument(
        "--observation-seed",
        type=int,
        default=None,
        help="Зафиксировать случайность экспедиции независимо от seed карты",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config/generation.json",
        help="JSON-файл с параметрами случайной генерации",
    )
    parser.add_argument(
        "--rocks",
        type=Path,
        default=PROJECT_ROOT / "config/rocks.json",
        help="JSON-файл со справочником пород и их признаками",
    )
    parser.add_argument(
        "--minerals",
        type=Path,
        default=PROJECT_ROOT / "config/minerals.json",
        help="JSON-файл со справочником полезных ископаемых",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output/map",
        help="Каталог для карты, наблюдений и автономного просмотрщика",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Зафиксировать seed; без параметра seed выбирается случайно",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.map is not None:
        with args.map.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if data.get("schema_version") not in {"2.0", "2.1", "2.2"} or data.get("map_kind") != "synthetic_ground_truth":
            raise ValueError("Ожидается истинная карта в формате 2.0, 2.1 или 2.2")
        mineral_catalog = json.loads(args.minerals.read_text(encoding="utf-8"))
        rock_catalog = json.loads(args.rocks.read_text(encoding="utf-8"))
        if "geophysics" not in data or args.recompute_geophysics:
            settings = json.loads(args.config.read_text(encoding="utf-8")).get("geophysics", {})
            add_geophysical_fields(data, settings, rock_catalog["rocks"], mineral_catalog["minerals"],
                                   replace=args.recompute_geophysics)
    else:
        config = load_config(args.config, args.rocks, args.minerals)
        data = generate_map(config, seed=args.seed)
        mineral_catalog = config
        rock_catalog = config
    observation_config = load_observation_config(args.observations_config)
    observation_seed = secrets.randbits(63) if args.observation_seed is None else args.observation_seed
    observations = generate_observations(data, observation_config, seed=observation_seed,
                                         mineral_catalog=mineral_catalog)
    recognition = recognize_deposits(observations, mineral_catalog, rock_catalog=rock_catalog)
    map_path = save_map(data, args.output / "map.json")
    observation_path = save_observations(observations, args.output / "observations")
    recognition_path = save_recognition(recognition, args.output / "recognition.json")
    internal_directory = args.output / "internal"
    internal_directory.mkdir(parents=True, exist_ok=True)
    (internal_directory / "expedition_run.json").write_text(
        json.dumps({"map_seed": data["seed"], "observation_seed": observation_seed,
                    "observation_config": observation_config}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    viewer_path = build_viewer(data, args.output / "map_view.html", observations=observations, recognition=recognition,
                               observation_config=observation_config, observation_seed=observation_seed)

    dimensions = data["dimensions"]
    statistics = data["statistics"]
    print("Истинная карта и разведочная экспедиция готовы")
    print(f"Seed: {data['seed']}")
    print(
        f"Размер: {dimensions['width_m']} × {dimensions['height_m']} × "
        f"{dimensions['depth_m']} м"
    )
    print(f"Ячеек: {statistics['cell_count']}")
    print(f"Слоёв: {statistics['layer_count']}")
    print(f"Месторождений: {statistics['deposit_count']}")
    print(f"Минерализованных ячеек: {statistics['mineralized_cell_count']}")
    print(f"Данные: {map_path}")
    print(f"Скважин в экспедиции: {observations['summary']['hole_count']}")
    print(f"Отобрано проб: {observations['summary']['sample_count']}")
    print(f"Почвенных проб: {observations['summary']['surface_sample_count']}")
    print(f"Наблюдений обнажений: {observations['summary']['outcrop_count']}")
    print(f"Точек съёмки рельефа: {observations['summary']['terrain_observation_count']}")
    print(f"Точек геофизической съёмки: {observations['summary']['geophysical_observation_count']}")
    print(f"Магнитных наблюдений: {observations['summary']['magnetic_observation_count']}")
    print(f"Гамма-наблюдений: {observations['summary']['gamma_observation_count']}")
    print(f"Измерений гамма-каротажа: {observations['summary']['gamma_log_count']}")
    print(f"Траншей: {observations['summary']['trench_count']}")
    print(f"Наблюдений зон разломов: {observations['summary']['fault_observation_count']}")
    print(f"Контрольных проб: {observations['summary']['qc_sample_count']}")
    print(f"Наблюдения: {observation_path}")
    print(f"Файлы отдельных объектов: {observation_path.parent / 'objects' / 'index.json'}")
    print(f"Минерализованных интервалов: {recognition['summary']['mineralized_intervals']}")
    print(f"Почвенных аномалий: {recognition['summary']['soil_anomalies']}")
    print(f"Целей с дополнительным признаком рельефа: {recognition['summary']['targets_supported_by_terrain']}")
    print(f"Геофизических аномалий: {recognition['summary']['geophysical_anomaly_count']}")
    print(f"Целей с поддержкой геофизики: {recognition['summary']['targets_supported_by_geophysics']}")
    print(f"Результат поиска: {recognition_path}")
    print(f"Просмотр: {viewer_path}")


if __name__ == "__main__":
    main()
