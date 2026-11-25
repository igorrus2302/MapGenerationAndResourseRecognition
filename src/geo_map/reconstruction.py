"""Reconstruct a bounded voxel model from public expedition records only.

The grid uses a common elevation datum, not distances along inclined holes.
A positive assay locates a mineralized intersection, not a proven block of ore.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .boreholes import point as borehole_point
from .geophysical_observations import geophysical_rows
from .resource_estimates import CoreDensities, estimate_zone_resources, reference_densities, summarize_resources


@dataclass(frozen=True)
class Grid:
    width: float
    height: float
    top: float
    bottom: float
    nx: int
    ny: int
    nz: int

    @property
    def steps(self):
        return self.width / self.nx, self.height / self.ny, (self.top - self.bottom) / self.nz

    @property
    def size(self):
        return self.nx * self.ny * self.nz

    def index(self, x, y, z):
        dx, dy, dz = self.steps
        if not (0 <= x <= self.width and 0 <= y <= self.height and 0 <= z <= self.top - self.bottom):
            return None
        return self.flat(min(int(x / dx), self.nx - 1), min(int(y / dy), self.ny - 1), min(int(z / dz), self.nz - 1))

    def flat(self, x, y, z):
        return (z * self.ny + y) * self.nx + x

    def axes(self, index):
        return index % self.nx, (index // self.nx) % self.ny, index // (self.nx * self.ny)

    def center(self, index):
        return tuple((i + .5) * step for i, step in zip(self.axes(index), self.steps))

    def segment(self, a, b):
        """Split a measured straight interval at every grid boundary."""
        cuts = {0., 1.}
        for start, end, step in zip(a, b, self.steps):
            if start == end:
                continue
            low, high = sorted((start, end))
            for k in range(math.floor(low / step) + 1, math.ceil(high / step)):
                t = (k * step - start) / (end - start)
                if 0 < t < 1:
                    cuts.add(t)
        cuts = sorted(cuts)
        for lo, hi in zip(cuts, cuts[1:]):
            mid = tuple(x + (y - x) * (lo + hi) / 2 for x, y in zip(a, b))
            index = self.index(*mid)
            if index is not None:
                yield index, mid, math.dist(a, b) * (hi - lo)

    def neighbors(self, index):
        x, y, z = self.axes(index)
        for xx, yy, zz in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
            if 0 <= xx < self.nx and 0 <= yy < self.ny and 0 <= zz < self.nz:
                yield self.flat(xx, yy, zz)


def _field_points(rows, field):
    return [(r['x_m'], r['y_m'], r[field]) for r in rows if r.get(field) is not None]


def _radius(width, height, count):
    return 1.5 * math.sqrt(width * height / max(1, count))


def _interpolate(points, x, y, radius):
    nearest = sorted(((math.hypot(px-x, py-y), value) for px, py, value in points), key=lambda p: p[0])[:4]
    if not nearest or nearest[0][0] > radius:
        return None
    if nearest[0][0] < 1e-7:
        return round(nearest[0][1], 4)
    weighted = [(1 / max(d, 1e-7)**2, v) for d, v in nearest if d <= radius]
    return round(sum(w*v for w,v in weighted) / sum(w for w,v in weighted), 4)


def _bracketed(xyz, positive_points, corridor):
    """Avoid expanding a body beyond the interval between two positive sites."""
    for a, b in combinations(positive_points, 2):
        direction = tuple(v-u for u,v in zip(a,b))
        squared_length = sum(v*v for v in direction)
        if squared_length < 1e-12:
            continue
        fraction = sum((p-u)*v for p,u,v in zip(xyz,a,direction)) / squared_length
        if 0 <= fraction <= 1:
            projection = tuple(u+fraction*v for u,v in zip(a,direction))
            if math.dist(xyz, projection) <= corridor:
                return True
    return False


def _valid_assay(row, failed):
    return (row.get('qc_type', 'primary') == 'primary' and row.get('qc_flag') != 'fail'
            and (row['sample_id'], row['analyte'], row['unit']) not in failed
            and row.get('result_qualifier') in (None, '', 'eq', 'lt'))


def _summarize_deposit_estimates(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count distinct reconstructed components by mineral, not observations."""
    by_mineral = defaultdict(list)
    for zone in zones:
        by_mineral[zone['mineral_id']].append(zone)

    estimates = []
    for mineral_id, mineral_zones in sorted(by_mineral.items()):
        first = mineral_zones[0]
        multi_site_count = sum(len(zone['sites']) >= 2 for zone in mineral_zones)
        estimates.append({
            'mineral_id': mineral_id,
            'name': first['name'],
            'analyte': first['analyte'],
            'color': first['color'],
            'estimated_deposit_count': len(mineral_zones),
            'multi_site_zone_count': multi_site_count,
            'single_site_zone_count': len(mineral_zones) - multi_site_count,
            'zone_ids': [zone['zone_id'] for zone in mineral_zones],
            'resources': summarize_resources([zone['resources'] for zone in mineral_zones]),
        })
    return estimates


def reconstruct_map(observations: dict[str, Any], targets: list[dict[str, Any]],
                    mineral_catalog: dict[str, Any], *,
                    rock_catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a spatial result without reading the generator configuration or true map."""
    campaign, tables = observations['campaign'], observations['tables']
    width, height = campaign['width_m'], campaign['height_m']
    holes = {r['hole_id']: r for r in tables.get('borehole_collars', [])}
    trenches = {r['trench_id']: r for r in tables.get('trenches', [])}
    terrain = _field_points(tables.get('terrain_observations', []), 'surface_elevation_m')
    outcrops = tables.get('outcrop_observations', [])
    # The published collar and outcrop elevations also constrain the surface.
    elevation_points = terrain + _field_points(holes.values(), 'collar_elevation_m') + _field_points(outcrops, 'surface_elevation_m')
    for method in ('magnetic', 'gamma'):
        if not terrain:
            elevation_points += _field_points(geophysical_rows(tables, method), 'surface_elevation_m')
    surface_radius = _radius(width, height, len(elevation_points))
    def surface(x, y):
        return _interpolate(elevation_points, x, y, surface_radius)

    def collar(h):
        return h.get('collar_elevation_m') if h.get('collar_elevation_m') is not None else (surface(h['x_m'], h['y_m']) or 0.)

    # Establish vertical coverage from actual survey elevations and drilled paths.
    elevations = [p[2] for p in elevation_points] or [0.]
    top = math.ceil(max(elevations) / 10) * 10
    lower = elevations + [collar(h) - borehole_point(h, h['total_depth_m'])[2] for h in holes.values()]
    lower += [min(elevations) - t.get('depth_m', 2.) for t in trenches.values()]
    bottom = min(top - 10, math.floor(min(lower) / 10) * 10)
    nx = max(1, min(60, max(4, math.ceil(width / 25))))
    ny = max(1, min(60, max(4, math.ceil(height / 25))))
    nz = max(1, min(100, math.ceil((top-bottom) / 10)))
    grid = Grid(width, height, top, bottom, nx, ny, nz)
    dx, dy, dz = grid.steps
    plane = nx * ny
    surface_values = [surface(*grid.center(i)[:2]) for i in range(plane)]
    # With no elevation observations, missing terrain stays unknown, not zero.
    fields = {}
    for method, field, unit in [('magnetic', 'magnetic_anomaly_nt', 'нТл'), ('gamma', 'gamma_count_rate_cps', 'имп/с')]:
        points = _field_points(geophysical_rows(tables, method), field)
        fields[method] = {'unit': unit, 'values': [_interpolate(points, *grid.center(i)[:2], _radius(width, height, len(points))) for i in range(plane)]}

    def path_point(source, site, distance, depth=None):
        if source == 'borehole':
            x, y, z = borehole_point(site, distance)
            return x, y, top - collar(site) + z
        f = distance / site['surveyed_length_m']
        x = site['start_x_m'] + f * (site['end_x_m'] - site['start_x_m'])
        y = site['start_y_m'] + f * (site['end_y_m'] - site['start_y_m'])
        return x, y, top - (surface(x, y) or 0.) + (site.get('depth_m', 2.) if depth is None else depth)

    def pieces(source, site, start, end, depth=None):
        # Short pieces follow the interpolated terrain for horizontal trenches.
        count = math.ceil((end-start) / max(1, min(dx,dy)/2)) if source == 'trench' else 1
        for k in range(max(1, count)):
            a = path_point(source, site, start+(end-start)*k/count, depth)
            b = path_point(source, site, start+(end-start)*(k+1)/count, depth)
            yield from grid.segment(a, b)

    paths = [('borehole', holes, 'hole_id', 'borehole_lithology', 'borehole_assays'),
             ('trench', trenches, 'trench_id', 'trench_intervals', 'trench_samples')]
    rocks = {r['id']: r for r in observations.get('rock_catalog', [])}
    logs_by_slice = defaultdict(list)
    direct_logs = defaultdict(Counter)
    # Each point represents an actual logged path portion in this voxel.
    for source, sites, site_key, log_table, _ in paths:
        for row in tables.get(log_table, []):
            site = sites.get(row[site_key])
            if site is None or row['to_m'] <= row['from_m']:
                continue
            rock = row['observed_rock_id']
            rocks.setdefault(rock, {'id': rock, 'name': row.get('observed_rock_name') or rock, 'color': '#9ca3af'})
            for index, position, length in pieces(source, site, row['from_m'], row['to_m']):
                direct_logs[index][rock] += length
                logs_by_slice[index//plane].append((position, (source, row[site_key]), rock))
    for row in outcrops:
        rock = row['observed_rock_id']
        rocks.setdefault(rock, {'id': rock, 'name': row.get('observed_rock_name') or rock, 'color': '#9ca3af'})
        elevation = row.get('surface_elevation_m')
        if elevation is None:
            elevation = surface(row['x_m'], row['y_m'])
        if elevation is None:
            continue
        p = (row['x_m'], row['y_m'], top-elevation+1e-7)
        index = grid.index(*p)
        if index is not None:
            direct_logs[index][rock] += 1
            logs_by_slice[index//plane].append((p, ('outcrop', row['observation_id']), rock))

    rock_list = [rocks[key] for key in sorted(rocks)]
    rock_index = {r['id']: i+1 for i,r in enumerate(rock_list)}
    lithology, support = [0]*grid.size, [0]*grid.size
    geology_radius = min(max(width, height), max(2*max(dx,dy), _radius(width,height,len(holes)+len(trenches))))
    for index in range(grid.size):
        x,y,z = grid.center(index)
        elevation = surface_values[index%plane]
        if index in direct_logs:
            votes = direct_logs[index]
            rock = min(votes, key=lambda r: (-votes[r], r))
            lithology[index], support[index] = rock_index[rock], 2
            continue
        if elevation is not None and top-z > elevation:
            support[index] = -1  # above the estimated ground
            continue
        # One vote per independent source, with inverse-distance weighting.
        nearest = {}
        for p, site, rock in logs_by_slice[index//plane]:
            d = math.dist((x,y,z), p)
            if d <= geology_radius and (site not in nearest or d < nearest[site][0]):
                nearest[site] = (d, rock)
        if not nearest or (len(nearest) == 1 and next(iter(nearest.values()))[0] > geology_radius/2):
            continue
        votes = Counter()
        for d, rock in sorted(nearest.values(), key=lambda item: item[0])[:6]:
            votes[rock] += 1 / max(d, min(dx,dy,dz)/2)**2
        rock = min(votes, key=lambda r: (-votes[r], r))
        lithology[index], support[index] = rock_index[rock], 1

    # Density information comes only from the observation bundle and public rock catalog.
    core_densities = CoreDensities(tables.get('downhole_properties', []))
    density_catalog = reference_densities(
        observations.get('rock_catalog', []) + (rock_catalog or {}).get('rocks', [])
    )
    reference_density_by_cell = {
        index: density_catalog[rock_list[code - 1]['id']]
        for index, code in enumerate(lithology)
        if code and rock_list[code - 1]['id'] in density_catalog
    }
    cell_volume = dx * dy * dz
    mineral_rules = {r['id']: r for r in mineral_catalog['minerals']}
    positive_targets = defaultdict(list)
    for target in targets:
        if target['kind'] == 'mineralized_interval':
            positive_targets[target['mineral_id']].append(target)
    failed = {(r['parent_sample_id'], r['analyte'], r['unit']) for r in tables.get('quality_control', [])
              if r['qc_type'] == 'duplicate' and r['qc_flag'] == 'fail'}
    zones = []
    mineral_radius = 2.5*max(dx,dy)
    corridor = math.hypot(dx,dy) / 2
    for mineral_id, mineral_targets in sorted(positive_targets.items()):
        rule = mineral_rules[mineral_id]
        threshold = rule['grade']['display_threshold']
        target_by_sample = { (t['source'], t['site_id'], sample): t for t in mineral_targets for sample in t['sample_ids'] }
        # Store only matching, usable analyses. Non-detects above the cutoff are unknown.
        points_by_slice = defaultdict(list)
        positive_cells = defaultdict(set)
        positives_by_slice = defaultdict(list)
        direct_grade_totals = defaultdict(lambda: [0.0, 0.0])
        direct_density_totals = defaultdict(lambda: [0.0, 0.0])
        for source, sites, site_key, _, assay_table in paths:
            for row in tables.get(assay_table, []):
                if (row['analyte'], row['unit']) != (rule['mineral'], rule['grade']['unit']) or not _valid_assay(row, failed):
                    continue
                site = sites.get(row[site_key])
                if site is None or row['to_m'] <= row['from_m']:
                    continue
                target = target_by_sample.get((source, row[site_key], row['sample_id']))
                censored = row.get('result_qualifier') == 'lt'
                if censored and row.get('detection_limit', row['result_value']) >= threshold:
                    continue
                grade = row.get('detection_limit', row['result_value']) if censored else row['result_value']
                depth = (row['sampling_depth_from_m']+row['sampling_depth_to_m'])/2 if source == 'trench' else None
                sample_density = (
                    core_densities.overlap(row[site_key], row['from_m'], row['to_m'])
                    if target and source == 'borehole' else (0.0, 0.0)
                )
                for index, position, length in pieces(source, site, row['from_m'], row['to_m'], depth):
                    if length <= 0:
                        continue
                    entry = (position, (source,row[site_key]), grade, target['target_id'] if target else None)
                    points_by_slice[index//plane].append(entry)
                    if target:
                        positive_cells[index].add(target['target_id'])
                        positives_by_slice[index//plane].append(entry)
                        direct_grade_totals[index][0] += grade * length
                        direct_grade_totals[index][1] += length
                        # Allocate the composite's measured density evidence in proportion
                        # to the part of the actual sample intersecting this model block.
                        portion = length / (row['to_m'] - row['from_m'])
                        direct_density_totals[index][0] += sample_density[0] * portion
                        direct_density_totals[index][1] += sample_density[1] * portion
        predicted = {index: (2, set(ids)) for index, ids in positive_cells.items()}
        grades_by_cell = {
            index: total / length
            for index, (total, length) in direct_grade_totals.items()
        }
        for layer, positives in positives_by_slice.items():
            if len({p[1] for p in positives}) < 2:
                continue  # No lateral extrapolation from a single intersection.
            if not positives:
                continue
            for index in range(layer*plane, (layer+1)*plane):
                if index in predicted or support[index] == -1:
                    continue
                xyz = grid.center(index)
                if all(math.dist(xyz,p[0]) > mineral_radius for p in positives):
                    continue
                nearest = {}
                for p, site, grade, target_id in points_by_slice[layer]:
                    distance = math.dist(xyz,p)
                    if distance <= mineral_radius and (site not in nearest or distance < nearest[site][0]):
                        nearest[site] = distance,grade,target_id,p
                yes = [entry for entry in nearest.values() if entry[2]]
                if len(yes) < 2 or not _bracketed(xyz, [entry[3] for entry in yes], corridor):
                    continue
                # Nearby measured negative intervals prevent bridging over them.
                if any(d <= min(p[0] for p in yes) for d,_,tid,_ in nearest.values() if tid is None):
                    continue
                weights = [1/max(d,min(dx,dy,dz)/2)**2 for d,_,_,_ in nearest.values()]
                grade = sum(w*entry[1] for w,entry in zip(weights,nearest.values()))/sum(weights)
                if grade >= threshold:
                    predicted[index] = (1,{p[2] for p in yes})
                    grades_by_cell[index] = grade
        target_lookup = {t['target_id']: t for t in mineral_targets}
        # Connected regions, with the same measured interval joining diagonal cells.
        by_target = defaultdict(set)
        for index,(status,ids) in predicted.items():
            if status == 2:
                for tid in ids:
                    by_target[tid].add(index)
        remaining = set(predicted)
        while remaining:
            first = min(remaining); remaining.remove(first)
            queue, component, ids = deque([first]), [], set()
            while queue:
                index = queue.popleft(); component.append(index)
                status, tids = predicted[index]; ids.update(tids)
                adjacent = set(grid.neighbors(index))
                if status == 2:
                    for tid in tids:
                        adjacent.update(by_target.pop(tid, ()))
                for other in sorted(adjacent & remaining):
                    remaining.remove(other); queue.append(other)
            evidence = [target_lookup[tid] for tid in sorted(ids)]
            axes = [grid.axes(i) for i in component]
            bounds = [(round(min(p[k] for p in axes)*step,4), round((max(p[k] for p in axes)+1)*step,4))
                      for k,step in enumerate(grid.steps)]
            observed = sum(predicted[i][0] == 2 for i in component)
            resources = estimate_zone_resources(
                cells=component,
                observed_count=observed,
                cell_volume_m3=cell_volume,
                grades_by_cell=grades_by_cell,
                density_evidence_by_cell=direct_density_totals,
                reference_density_by_cell=reference_density_by_cell,
                grade_unit=rule['grade']['unit'],
            )
            zones.append({'zone_id': f'ZONE-{len(zones)+1:04d}', 'mineral_id': mineral_id,
                          'name': rule['name'], 'analyte': rule['mineral'], 'color': rule['color'],
                          'unit': rule['grade']['unit'], 'threshold': threshold,
                          'peak_measured_grade': max(t['peak_result'] for t in evidence),
                          'target_ids': sorted(ids), 'sites': sorted({t['site_id'] for t in evidence}),
                          'sample_count': len({(t['source'],t['site_id'],s) for t in evidence for s in t['sample_ids']}),
                          'measured_intervals': [{key: t[key] for key in
                                                  ('target_id', 'source', 'site_id', 'from_m', 'to_m',
                                                   'sample_ids', 'peak_result', 'supporting_signals',
                                                   'qc_warning_sample_ids', 'laboratory_alerts')}
                                                 for t in evidence],
                          'signals': sorted({s for t in evidence for s in t['supporting_signals']}),
                          'bounds_m': {'x': bounds[0], 'y': bounds[1], 'elevation': [top-bounds[2][1],top-bounds[2][0]]},
                          'observed_cell_count': observed, 'interpolated_cell_count': len(component)-observed,
                          'resources': resources,
                          'cells': [[i,predicted[i][0]] for i in sorted(component)]})

    deposit_estimates = _summarize_deposit_estimates(zones)
    return {'data_kind': 'reconstructed_geological_map', 'schema_version': '1.2', 'campaign': campaign,
            'dimensions': {'width_m': width,'height_m': height,'top_elevation_m': top,'bottom_elevation_m': bottom,
                           'width_cells': nx,'height_cells': ny,'depth_cells': nz,'cell_size_x_m': dx,'cell_size_y_m': dy,'depth_step_m': dz},
            'grid_order': 'z_y_x', 'vertical_reference': 'common_observed_elevation_datum',
            'rock_catalog': rock_list, 'lithology': lithology, 'lithology_support': support,
            'surface_elevation_m': surface_values, 'geophysical_fields': fields,
            'mineral_zones': zones, 'mineral_deposit_estimates': deposit_estimates,
            'soil_anomalies': [t for t in targets if t['kind']=='soil_anomaly'],
            'parameters': {'geology_radius_m': geology_radius,'mineral_radius_m': mineral_radius,
                           'minimum_interpolation_sites': 2, 'mineral_corridor_m': corridor, 'rock_codes': '0=unknown; 1-based index into rock_catalog',
                           'support_codes': '-1=above_surface; 0=unknown; 1=interpolated; 2=intersects_observation'},
            'summary': {'cell_count': grid.size,'observed_lithology_cells': support.count(2),
                        'interpolated_lithology_cells': support.count(1),'unknown_cells': support.count(0),
                        'above_surface_cells': support.count(-1),'mineral_zone_count': len(zones),
                        'estimated_deposit_count': len(zones), 'mineral_types': len(deposit_estimates),
                        'unplaced_target_count': len({t['target_id'] for group in positive_targets.values() for t in group} - {target for z in zones for target in z['target_ids']}),
                        'observed_mineral_cells': sum(z['observed_cell_count'] for z in zones),
                        'interpolated_mineral_cells': sum(z['interpolated_cell_count'] for z in zones)}}
