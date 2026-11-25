"""Indicative in-place resource quantities for the reconstructed block model.

All selected blocks are assumed to be filled for this geometric estimate.
An observed intersection does not demonstrate full mineralization of a block.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


class CoreDensities:
    """Index accepted density measurements by borehole and measured interval."""

    def __init__(self, measurements: list[dict[str, Any]]) -> None:
        self.by_hole = defaultdict(list)
        for row in measurements:
            density = row.get('density_g_cm3')
            start, end = row.get('from_m'), row.get('to_m')
            if (row.get('qc_flag') != 'fail' and _positive_number(density)
                    and isinstance(start, (int, float)) and isinstance(end, (int, float))
                    and math.isfinite(start) and math.isfinite(end) and end > start):
                self.by_hole[row['hole_id']].append(row)

    def overlap(self, hole_id: str, start: float, end: float) -> tuple[float, float]:
        """Return density times overlap length, and the measured overlap length."""
        weighted_density = measured_length = 0.0
        for row in self.by_hole[hole_id]:
            overlap = max(0.0, min(end, row['to_m']) - max(start, row['from_m']))
            weighted_density += overlap * row['density_g_cm3']
            measured_length += overlap
        return weighted_density, measured_length


def reference_densities(rocks: list[dict[str, Any]]) -> dict[str, float]:
    """Use the midpoint of catalogued density ranges as a fallback, in t/m³."""
    densities = {}
    for rock in rocks:
        value = rock.get('density_g_cm3')
        if _positive_number(value):
            densities[rock['id']] = float(value)
        elif isinstance(value, (list, tuple)) and len(value) == 2 and all(map(_positive_number, value)):
            densities[rock['id']] = sum(value) / 2
    return densities


def grade_mass_fraction(grade: float, unit: str) -> float | None:
    """Convert the assay unit into tonnes of reported component per tonne of rock."""
    unit = unit.strip().lower()
    if unit.startswith('%'):
        fraction = grade / 100
    elif unit == 'g/t' or unit.startswith('g/t ') or unit == 'ppm' or unit.startswith('ppm '):
        fraction = grade / 1_000_000
    elif unit == 'ct/t' or unit.startswith('ct/t '):
        fraction = grade * 0.2 / 1_000_000  # 1 metric carat = 0.2 gram.
    else:
        return None
    return fraction if math.isfinite(fraction) and 0 <= fraction <= 1 else None


def estimate_zone_resources(
    *,
    cells: list[int],
    observed_count: int,
    cell_volume_m3: float,
    grades_by_cell: dict[int, float],
    density_evidence_by_cell: dict[int, tuple[float, float]],
    reference_density_by_cell: dict[int, float],
    grade_unit: str,
) -> dict[str, Any]:
    """Calculate volume, representative density, ore mass and component mass."""
    volume = len(cells) * cell_volume_m3
    observed_volume = observed_count * cell_volume_m3

    # The same representative bulk density is used for every mineralized block.
    # Prefer accepted core measurements overlapping the positive sample intervals.
    weighted_density = measured_length = 0.0
    for index in cells:
        numerator, length = density_evidence_by_cell.get(index, (0.0, 0.0))
        weighted_density += numerator
        measured_length += length
    if measured_length > 0:
        density = weighted_density / measured_length
        density_source = 'measured_core'
    else:
        reference = [reference_density_by_cell[index] for index in cells if index in reference_density_by_cell]
        density = sum(reference) / len(reference) if reference else None
        density_source = 'rock_catalog' if reference else 'unavailable'

    # Equal block volumes and a representative constant density make the
    # arithmetic mean of estimated block grades the mass-weighted model mean.
    average_grade = sum(grades_by_cell[index] for index in cells) / len(cells)
    ore_mass = volume * density if density is not None else None
    fraction = grade_mass_fraction(average_grade, grade_unit)
    component_mass = ore_mass * fraction if ore_mass is not None and fraction is not None else None
    return {
        'volume_m3': volume,
        'observed_cells_volume_m3': observed_volume,
        'interpolated_cells_volume_m3': volume - observed_volume,
        'density_t_m3': density,
        'density_source': density_source,
        'density_measured_length_m': measured_length,
        'ore_mass_t': ore_mass,
        'average_grade': average_grade,
        'grade_unit': grade_unit,
        'component_mass_t': component_mass,
        'volume_method': 'full_reconstructed_cells',
    }


def summarize_resources(estimates: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate disjoint zones of one mineral without treating unknown masses as zero."""
    def total_if_known(field: str) -> float | None:
        values = [entry[field] for entry in estimates]
        return sum(values) if all(value is not None for value in values) else None

    volume = sum(entry['volume_m3'] for entry in estimates)
    ore_mass = total_if_known('ore_mass_t')
    component_mass = total_if_known('component_mass_t')
    average_grade = (
        sum(entry['average_grade'] * entry['ore_mass_t'] for entry in estimates) / ore_mass
        if ore_mass is not None and ore_mass > 0 else None
    )
    return {
        'volume_m3': volume,
        'observed_cells_volume_m3': sum(entry['observed_cells_volume_m3'] for entry in estimates),
        'interpolated_cells_volume_m3': sum(entry['interpolated_cells_volume_m3'] for entry in estimates),
        'density_t_m3': ore_mass / volume if ore_mass is not None and volume > 0 else None,
        'ore_mass_t': ore_mass,
        'average_grade': average_grade,
        'grade_unit': estimates[0]['grade_unit'],
        'component_mass_t': component_mass,
        'zones_without_density': sum(entry['density_t_m3'] is None for entry in estimates),
        'volume_method': 'full_reconstructed_cells',
    }
