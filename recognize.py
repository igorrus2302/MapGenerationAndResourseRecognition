"""Search an existing expedition without loading its ground-truth map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main import PROJECT_ROOT
from geo_map.geophysical_observations import GEOPHYSICAL_DIRECTORIES, GEOPHYSICAL_TABLES, load_geophysical_csv
from geo_map.recognition import recognize_deposits, save_recognition


def main() -> None:
    parser = argparse.ArgumentParser(description="Поиск полезных ископаемых по наблюдениям экспедиции")
    parser.add_argument("--observations", type=Path, default=PROJECT_ROOT / "output/map/observations/observations.json",
                        help="Сводный observations.json существующей экспедиции")
    parser.add_argument("--magnetic-observations", type=Path, help="Отдельный CSV магнитной съёмки")
    parser.add_argument("--gamma-observations", type=Path, help="Отдельный CSV гамма-съёмки")
    parser.add_argument("--minerals", type=Path, default=PROJECT_ROOT / "config/minerals.json",
                        help="Справочник поисковых порогов и геологических признаков")
    parser.add_argument("--rocks", type=Path, default=PROJECT_ROOT / "config/rocks.json",
                        help="Справочник диапазонов плотности и пористости пород")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output/map/recognition.json",
                        help="JSON с выделенными интервалами и почвенными аномалиями")
    parser.add_argument("--reconstructed-map", type=Path,
                        help="Отдельный JSON восстановленной карты (по умолчанию reconstructed_map.json рядом с результатом)")
    args = parser.parse_args()
    reconstructed_path = args.reconstructed_map or args.output.with_name("reconstructed_map.json")
    channel_paths = {}
    for method, table in GEOPHYSICAL_TABLES.items():
        path = getattr(args, f"{method}_observations")
        if path is None:
            candidate = args.observations.parent / "tables" / GEOPHYSICAL_DIRECTORIES[table] / f"{table}.csv"
            if candidate.is_file():
                path = candidate
        if path is not None:
            channel_paths[method] = path
    inputs = (args.observations, args.minerals, args.rocks, *channel_paths.values())
    input_paths = {path.resolve() for path in inputs}
    output_paths = {args.output.resolve(), reconstructed_path.resolve()}
    if len(output_paths) != 2 or input_paths & output_paths:
        parser.error("Выходные файлы должны отличаться друг от друга и от входных файлов")
    try:
        observations = json.loads(args.observations.read_text(encoding="utf-8"))
        for method, path in channel_paths.items():
            observations["tables"][GEOPHYSICAL_TABLES[method]] = load_geophysical_csv(
                path, method, observations["campaign"]["campaign_id"])
        catalog = json.loads(args.minerals.read_text(encoding="utf-8"))
        rocks = json.loads(args.rocks.read_text(encoding="utf-8"))
        result = recognize_deposits(observations, catalog, rock_catalog=rocks)
        output = save_recognition(result, args.output)
        reconstructed = save_recognition(result["reconstructed_map"], reconstructed_path)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Ошибка поиска: {error}\n")
    summary = result["summary"]
    print(f"Минерализованных интервалов: {summary['mineralized_intervals']}")
    print(f"Почвенных аномалий: {summary['soil_anomalies']}")
    print(f"Целей с дополнительным признаком рельефа: {summary['targets_supported_by_terrain']}")
    print(f"Геофизических аномалий: {summary['geophysical_anomaly_count']}")
    print(f"Целей с поддержкой геофизики: {summary['targets_supported_by_geophysics']}")
    print(f"Результат поиска: {output}")
    print(f"Реконструированная карта: {reconstructed}")
    print(f"Выделено пространственных рудных зон: {result['reconstructed_map']['summary']['mineral_zone_count']}")


if __name__ == "__main__":
    main()
