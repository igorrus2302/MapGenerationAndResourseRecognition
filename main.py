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
        if data.get("schema_version") != "2.0" or data.get("map_kind") != "synthetic_ground_truth":
            raise ValueError("Ожидается истинная карта в формате 2.0")
    else:
        config = load_config(args.config, args.rocks, args.minerals)
        data = generate_map(config, seed=args.seed)
    observation_config = load_observation_config(args.observations_config)
    observation_seed = secrets.randbits(63) if args.observation_seed is None else args.observation_seed
    observations = generate_observations(data, observation_config, seed=observation_seed)
    map_path = save_map(data, args.output / "map.json")
    observation_path = save_observations(observations, args.output / "observations")
    internal_directory = args.output / "internal"
    internal_directory.mkdir(parents=True, exist_ok=True)
    (internal_directory / "expedition_run.json").write_text(
        json.dumps({"map_seed": data["seed"], "observation_seed": observation_seed,
                    "observation_config": observation_config}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    viewer_path = build_viewer(data, args.output / "map_view.html", observations=observations)

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
    print(f"Траншей: {observations['summary']['trench_count']}")
    print(f"Наблюдений зон разломов: {observations['summary']['fault_observation_count']}")
    print(f"Контрольных проб: {observations['summary']['qc_sample_count']}")
    print(f"Наблюдения: {observation_path}")
    print(f"Просмотр: {viewer_path}")


if __name__ == "__main__":
    main()
