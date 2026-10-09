from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from geo_map import build_viewer, generate_map, load_config, save_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генерация минимальной синтетической геологической карты"
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
        help="Каталог для map.json и map_view.html",
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
    config = load_config(args.config, args.rocks, args.minerals)
    data = generate_map(config, seed=args.seed)
    map_path = save_map(data, args.output / "map.json")
    viewer_path = build_viewer(data, args.output / "map_view.html")

    dimensions = data["dimensions"]
    statistics = data["statistics"]
    print("Карта успешно сгенерирована")
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
    print(f"Просмотр: {viewer_path}")


if __name__ == "__main__":
    main()
