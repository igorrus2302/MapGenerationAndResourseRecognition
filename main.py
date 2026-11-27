from __future__ import annotations

import argparse
import json
import secrets
import shutil
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
from geo_map.observations import generate_preliminary_observations, save_preliminary_observations
from geo_map.workspace_server import serve_workspace


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
    parser.add_argument("--batch", action="store_true",
                        help="Сразу сформировать и сохранить всю экспедицию без интерактивного запуска")
    parser.add_argument("--port", type=int, default=0,
                        help="Порт локального просмотрщика (0 — выбрать свободный)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Не открывать браузер автоматически")
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
    prepare_run_output(data, args.output, input_paths=(args.map, args.config, args.rocks,
                                                      args.minerals, args.observations_config))

    def collect_preliminary() -> dict:
        preliminary = generate_preliminary_observations(data, observation_config, seed=observation_seed)
        path = save_preliminary_observations(preliminary, args.output / "observations")
        print(f"Предварительные наблюдения сохранены: {path}", flush=True)
        print("Для запуска разведочной экспедиции нажмите кнопку на вкладке 03.", flush=True)
        return preliminary

    def collect(preliminary_tables=None) -> Path:
        return run_expedition(data, args.output, observation_config, observation_seed,
                              mineral_catalog, rock_catalog, preliminary_collected=not args.batch,
                              preliminary_tables=preliminary_tables)

    if args.batch:
        collect()
    else:
        serve_workspace(data, observation_config, observation_seed, collect_preliminary, collect,
                        port=args.port, open_browser=not args.no_browser)


def prepare_run_output(data: dict, output: Path, *, input_paths: tuple[Path | None, ...] = ()) -> None:
    """Remove previous generated results before exposing the new truth map."""
    generated_directories = ("observations", "internal")
    generated_files = ("recognition.json", "reconstructed_map.json", "map_view.html", "map.json")
    root = output.resolve()
    for source in input_paths:
        if source is None:
            continue
        source = source.resolve()
        if source == root / "map.json":
            continue  # The current truth map is already loaded in memory.
        if any(source.is_relative_to(root / name) for name in (*generated_directories, *generated_files)):
            raise ValueError(f"Входной файл находится в каталоге очищаемых результатов: {source}")
    for name in generated_files:
        path = output / name
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"Вместо файла результата найден каталог: {path}")

    output.mkdir(parents=True, exist_ok=True)
    for name in (*generated_directories, *generated_files):
        path = output / name
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    # The input map (including --map output/map/map.json) has already been
    # loaded, so the new run always has its own current truth map on disk.
    save_map(data, output / "map.json")


def run_expedition(data: dict, output: Path, observation_config: dict, observation_seed: int,
                   mineral_catalog: dict, rock_catalog: dict, *, preliminary_collected: bool,
                   preliminary_tables: dict | None = None) -> Path:
    """Generate all dependent stages after collection is requested, and persist the result."""
    observations = generate_observations(data, observation_config, seed=observation_seed,
                                         mineral_catalog=mineral_catalog, preliminary_tables=preliminary_tables)
    recognition = recognize_deposits(observations, mineral_catalog, rock_catalog=rock_catalog)
    map_path = save_map(data, output / "map.json")
    observation_path = save_observations(observations, output / "observations")
    recognition_path = save_recognition(recognition, output / "recognition.json")
    reconstruction_path = save_recognition(recognition["reconstructed_map"], output / "reconstructed_map.json")
    internal_directory = output / "internal"
    internal_directory.mkdir(parents=True, exist_ok=True)
    (internal_directory / "expedition_run.json").write_text(
        json.dumps({"map_seed": data["seed"], "observation_seed": observation_seed,
                    "observation_config": observation_config}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    viewer_path = build_viewer(data, output / "map_view.html", observations=observations, recognition=recognition,
                               observation_config=observation_config, observation_seed=observation_seed,
                               preliminary_collected=preliminary_collected)

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
    print(f"Измерений магнитного каротажа: {observations['summary']['magnetic_log_count']}")
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
    print(f"Аномалий магнитного каротажа: {recognition['summary']['downhole_magnetic_anomaly_count']}")
    print(f"Целей с поддержкой магнитного каротажа: {recognition['summary']['targets_supported_by_downhole_magnetic']}")
    print(f"Результат поиска: {recognition_path}")
    print(f"Реконструированная карта: {reconstruction_path}")
    print(f"Выделено пространственных рудных зон: {recognition['reconstructed_map']['summary']['mineral_zone_count']}")
    print(f"Просмотр: {viewer_path}", flush=True)
    return viewer_path


if __name__ == "__main__":
    main()
