"""Tests for independent, observation-only spatial reconstruction."""
import json
import unittest
from copy import deepcopy

from test_observations import ROOT, campaign_config, small_map
from geo_map.observations import generate_observations
from geo_map.recognition import recognize_deposits
from geo_map.resource_estimates import grade_mass_fraction, summarize_resources


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'config/minerals.json').read_text())
        self.bundle = generate_observations(small_map(), campaign_config(), seed=1)

    def result(self):
        return recognize_deposits(self.bundle, self.catalog)['reconstructed_map']

    def test_reconstruction_is_spatial_and_independent(self):
        model = self.result()
        d = model['dimensions']
        self.assertEqual(model['data_kind'], 'reconstructed_geological_map')
        self.assertEqual(d['width_m'], 20)
        self.assertEqual(d['height_m'], 10)
        self.assertEqual(model['grid_order'], 'z_y_x')
        self.assertEqual(len(model['lithology']), d['width_cells'] * d['height_cells'] * d['depth_cells'])
        self.assertEqual(len(model['lithology']), len(model['lithology_support']))
        self.assertGreater(model['summary']['observed_lithology_cells'], 0)
        self.assertGreater(model['summary']['interpolated_lithology_cells'], 0)
        self.assertGreater(model['summary']['observed_mineral_cells'], 0)
        self.assertEqual(model['summary']['interpolated_mineral_cells'], 0)
        self.assertNotIn('SECRET-DEPOSIT', json.dumps(model))
        self.assertEqual(model, self.result())

    def test_single_hole_does_not_extrapolate_minerals(self):
        self.assertTrue(all(z['sites'] == ['BH-001'] for z in self.result()['mineral_zones']))
        self.assertTrue(all(status == 2 for z in self.result()['mineral_zones'] for _, status in z['cells']))

    def test_adjacent_positive_independent_holes_form_one_zone(self):
        rows = self.bundle['tables']['borehole_assays']
        for row in rows:
            row['result_qualifier'] = None
            row['result_value'] = 0.6 if row['from_m'] < 10 else 0.
        model = self.result()
        self.assertEqual(len(model['mineral_zones']), 1)
        zone = model['mineral_zones'][0]
        self.assertEqual(zone['sites'], ['BH-001', 'BH-002'])
        self.assertGreater(zone['interpolated_cell_count'], 0)
        self.assertEqual(zone['sample_count'], 4)
        self.assertEqual(zone['peak_measured_grade'], 0.6)
        estimate = model['mineral_deposit_estimates'][0]
        self.assertEqual(estimate['estimated_deposit_count'], 1)
        self.assertEqual(estimate['multi_site_zone_count'], 1)
        self.assertEqual(estimate['single_site_zone_count'], 0)
        self.assertEqual(estimate['zone_ids'], [zone['zone_id']])

    def test_deposit_count_groups_disconnected_zones_by_mineral(self):
        # Move the second observation far enough away that interpolation cannot link
        # the copper intersections. Include a separate iron finding as well.
        self.bundle['campaign']['width_m'] = 200
        self.bundle['tables']['borehole_collars'][1]['x_m'] = 185
        for row in self.bundle['tables']['borehole_assays']:
            row['result_qualifier'] = None
            row['result_value'] = 0.6 if row['from_m'] < 10 else 0.
            if row['hole_id'] == 'BH-001' and row['from_m'] == 15:
                row.update(analyte='Fe', unit='% Fe', result_value=30.)
        model = self.result()
        estimates = {e['mineral_id']: e for e in model['mineral_deposit_estimates']}
        self.assertEqual(estimates['copper']['estimated_deposit_count'], 2)
        self.assertEqual(estimates['copper']['single_site_zone_count'], 2)
        self.assertEqual(estimates['copper']['multi_site_zone_count'], 0)
        self.assertEqual(estimates['iron']['estimated_deposit_count'], 1)
        self.assertEqual(model['summary']['estimated_deposit_count'], 3)
        self.assertEqual(model['summary']['mineral_types'], 2)
        self.assertAlmostEqual(estimates['copper']['resources']['volume_m3'],
                               sum(z['resources']['volume_m3'] for z in model['mineral_zones'] if z['mineral_id'] == 'copper'))
        self.assertAlmostEqual(estimates['copper']['resources']['ore_mass_t'],
                               sum(z['resources']['ore_mass_t'] for z in model['mineral_zones'] if z['mineral_id'] == 'copper'))
        self.assertEqual(
            {zone_id for e in estimates.values() for zone_id in e['zone_ids']},
            {zone['zone_id'] for zone in model['mineral_zones']},
        )

    def test_resource_estimate_uses_block_volume_core_density_and_mean_grade(self):
        for row in self.bundle['tables']['borehole_assays']:
            row['result_qualifier'] = None
            row['result_value'] = 0.6 if row['from_m'] < 10 else 0.
        for row in self.bundle['tables']['downhole_properties']:
            row['density_g_cm3'] = 2.5 if row['from_m'] < 10 else 10.
        model = self.result()
        zone = model['mineral_zones'][0]
        estimate = zone['resources']
        dims = model['dimensions']
        cell_volume = dims['cell_size_x_m'] * dims['cell_size_y_m'] * dims['depth_step_m']
        expected_volume = len(zone['cells']) * cell_volume
        self.assertAlmostEqual(estimate['volume_m3'], expected_volume)
        self.assertAlmostEqual(estimate['observed_cells_volume_m3'] + estimate['interpolated_cells_volume_m3'], expected_volume)
        self.assertAlmostEqual(estimate['density_t_m3'], 2.5)
        self.assertAlmostEqual(estimate['ore_mass_t'], expected_volume * 2.5)
        self.assertAlmostEqual(estimate['average_grade'], 0.6)
        self.assertAlmostEqual(estimate['component_mass_t'], expected_volume * 2.5 * 0.006)
        self.assertEqual(estimate['density_source'], 'measured_core')
        totals = model['mineral_deposit_estimates'][0]['resources']
        self.assertAlmostEqual(totals['component_mass_t'], estimate['component_mass_t'])
        self.assertEqual(totals['zones_without_density'], 0)

    def test_missing_core_density_uses_catalog_or_leaves_mass_unknown(self):
        # Failed density measurements must not be used to estimate ore tonnage.
        for row in self.bundle['tables']['downhole_properties']:
            row['qc_flag'] = 'fail'
            row['density_g_cm3'] = 99.
        model = self.result()
        zone = model['mineral_zones'][0]['resources']
        self.assertGreater(zone['volume_m3'], 0)
        self.assertIsNone(zone['ore_mass_t'])
        self.assertIsNone(zone['component_mass_t'])
        self.assertEqual(zone['density_source'], 'unavailable')
        catalog = {'rocks': [
            {'id': 'a', 'density_g_cm3': [2., 4.]},
            {'id': 'b', 'density_g_cm3': [2., 4.]}
        ]}
        model = recognize_deposits(self.bundle, self.catalog, rock_catalog=catalog)['reconstructed_map']
        zone = model['mineral_zones'][0]['resources']
        self.assertEqual(zone['density_source'], 'rock_catalog')
        self.assertAlmostEqual(zone['ore_mass_t'], zone['volume_m3'] * 3.)

    def test_grade_mass_units_and_unknown_aggregate_mass(self):
        self.assertAlmostEqual(grade_mass_fraction(5., '% Cu'), 0.05)
        self.assertAlmostEqual(grade_mass_fraction(5., 'g/t Au'), 0.000005)
        self.assertAlmostEqual(grade_mass_fraction(5., 'ct/t'), 0.000001)
        self.assertIsNone(grade_mass_fraction(5., 'unknown'))
        self.assertIsNone(grade_mass_fraction(120., '% Cu'))
        # A total must not imply that an unquantified zone has zero mass.
        known = {'volume_m3': 100., 'observed_cells_volume_m3': 40.,
                 'interpolated_cells_volume_m3': 60., 'density_t_m3': 2.,
                 'ore_mass_t': 200., 'average_grade': 1., 'grade_unit': '% Cu',
                 'component_mass_t': 2.}
        unknown = {**known, 'density_t_m3': None, 'ore_mass_t': None, 'component_mass_t': None}
        total = summarize_resources([known, unknown])
        self.assertEqual(total['volume_m3'], 200.)
        self.assertIsNone(total['ore_mass_t'])
        self.assertIsNone(total['component_mass_t'])
        self.assertEqual(total['zones_without_density'], 1)

    def test_failed_and_censored_assays_never_create_positive_cells(self):
        rows = self.bundle['tables']['borehole_assays']
        for row in rows:
            row['result_value'] = 1.
            row['result_qualifier'] = 'lt'
        self.bundle['tables']['quality_control'] = [{
            'qc_type':'duplicate', 'qc_flag':'fail', 'parent_sample_id':rows[0]['sample_id'],
            'analyte':'Cu', 'unit':'% Cu'
        }]
        rows[0]['result_qualifier'] = None
        self.assertEqual(self.result()['mineral_zones'], [])

    def test_borehole_elevation_controls_grid_position(self):
        self.bundle['tables']['borehole_collars'][0]['collar_elevation_m'] = 50
        model = self.result()
        self.assertEqual(model['dimensions']['top_elevation_m'], 50)
        self.assertTrue(all(z['bounds_m']['elevation'][0] >= 30 for z in model['mineral_zones']))

    def test_empty_campaign_marks_cells_unknown(self):
        for table in self.bundle['tables']:
            self.bundle['tables'][table] = []
        model = self.result()
        self.assertEqual(model['summary']['unknown_cells'], model['summary']['cell_count'])
        self.assertEqual(model['mineral_zones'], [])
        self.assertEqual(model['mineral_deposit_estimates'], [])
        self.assertEqual(model['summary']['estimated_deposit_count'], 0)
        self.assertTrue(all(v is None for v in model['surface_elevation_m']))
        self.assertTrue(all(v is None for v in model['geophysical_fields']['magnetic']['values']))

    def test_outcrops_and_geophysics_are_used_without_becoming_ore(self):
        for table in self.bundle['tables']:
            self.bundle['tables'][table] = []
        self.bundle['tables']['outcrop_observations'] = [{
            'observation_id':'O-1','x_m':5,'y_m':5,'surface_elevation_m':0,
            'observed_rock_id':'a','observed_rock_name':'Песчаник'
        }]
        self.bundle['tables']['magnetic_observations'] = [{
            'observation_id':'M-1','x_m':5,'y_m':5,'surface_elevation_m':0,
            'magnetic_anomaly_nt':20,'magnetic_sigma_nt':1
        }]
        model = self.result()
        self.assertEqual(model['summary']['observed_lithology_cells'], 1)
        self.assertIn(20, model['geophysical_fields']['magnetic']['values'])
        self.assertEqual(model['mineral_zones'], [])


if __name__ == '__main__':
    unittest.main()
