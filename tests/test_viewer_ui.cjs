// Source-level interaction checks. DOM doubles do not validate visual layout.
// Run after main.py: node tests/test_viewer_ui.cjs output/map/map_view.html
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync(process.argv[2] || 'output/map/map_view.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
assert.equal(scripts.length, 1);

class Element {
  constructor(attributes = {}) {
    this.attributes = attributes;
    this.dataset = Object.fromEntries(Object.entries(attributes).filter(([key]) => key.startsWith('data-')).map(([key, value]) => [key.slice(5), value]));
    this.value = attributes.value || '';
    this.style = {};
    this.children = [];
    this.listeners = {};
    const classes = new Set((attributes.class || '').split(/\s+/));
    this.classList = {
      contains: value => classes.has(value),
      add: value => classes.add(value),
      remove: value => classes.delete(value),
      toggle: (value, force) => {
        const enabled = force === undefined ? !classes.has(value) : force;
        if (enabled) classes.add(value); else classes.delete(value);
      },
    };
  }
  set innerHTML(value) {
    this.markup = value;
    this.children = [];
    const option = value.match(/<option value="([^"]*)"/);
    if (option) this.value = option[1];
  }
  get innerHTML() { return this.markup || ''; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  fire(name, event = {}) { for (const callback of this.listeners[name] || []) callback({preventDefault() {}, ...event}); }
  click() { this.fire('click'); }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(child) { this.children.push(child); }
  querySelector() { return new Element(); }
  getContext() { return new Proxy({createLinearGradient: () => ({addColorStop() {}})}, {get: (target, key) => target[key] ?? (() => {})}); }
  getBoundingClientRect() { return {width: 0, height: 0}; }
  focus() {}
}

const nodes = new Map();
const all = [];
for (const match of html.matchAll(/<([a-z][\w-]*)\b([^>]*)>/g)) {
  const attrs = Object.fromEntries([...match[2].matchAll(/([\w-]+)="([^"]*)"/g)].map(attribute => [attribute[1], attribute[2]]));
  if (!attrs.id && !attrs['data-workspace']) continue;
  const node = new Element(attrs);
  all.push(node);
  if (attrs.id) nodes.set(attrs.id, node);
}
for (const match of html.matchAll(/<select\b([^>]*)>([\s\S]*?)<\/select>/g)) {
  const id = match[1].match(/id="([^"]*)"/)[1];
  nodes.get(id).innerHTML = match[2];
}
const get = id => {
  assert.ok(nodes.has(id), `Missing element #${id}`);
  return nodes.get(id);
};
function clickMapPoint(map, attribute, identifier) {
  get(map).fire('click', {target: {closest: selector => selector === `[data-${attribute}]` ? {dataset: {[attribute]: identifier}} : null}});
}
const blobs = [];
const location = {hash: ''};
const context = vm.createContext({
  document: {
    getElementById: get,
    createElement: () => new Element(),
    querySelectorAll: selector => all.filter(node => selector === '.workspace-tab' ? node.classList.contains('workspace-tab') : node.dataset.workspace),
  },
  window: {devicePixelRatio: 1, addEventListener() {}},
  location,
  history: {replaceState(_state, _title, hash) { location.hash = hash; }},
  requestAnimationFrame() {},
  ResizeObserver: class { observe() {} },
  Blob,
  URL: {createObjectURL(blob) { blobs.push(blob); return `blob:${blobs.length}`; }, revokeObjectURL() {}},
  setTimeout() {},
});
new vm.Script(scripts[0]).runInContext(context);
const observations = vm.runInContext('OBSERVATION_DATA', context);
const preliminaryPlan = vm.runInContext('PRELIMINARY_PLAN', context);
if (vm.runInContext('Boolean(MAP_DATA.terrain)', context)) {
  const canvas = get('mapCanvas');
  canvas.clientWidth = 960;
  canvas.clientHeight = 650;
  canvas.getBoundingClientRect = () => ({left: 0, top: 0});
  const target = vm.runInContext(`(() => {
    state.mode = 'terrain'; updateControls(); render();
    const {geometry} = state.hitMap;
    const cell = cells.find(item => item.intervals[0].rock_id !== terrain.surface_cover_rock_id) ?? cells[0];
    return {name: rockById[cell.intervals[0].rock_id].name,
      clientX: geometry.left + (cell.x_index + .5) * dims.cell_size_m * geometry.cellSize,
      clientY: geometry.top + (dims.height_cells - cell.y_index - .5) * dims.cell_size_m * geometry.cellSize};
  })()`, context);
  canvas.fire('click', target);
  assert.ok(get('cellInfo').innerHTML.includes(target.name));
  assert.ok(get('cellInfo').innerHTML.includes('Отметка поверхности'));
  vm.runInContext("state.mode = 'vertical-x'; updateControls(); render(); state.mode = '3d'; updateControls(); render()", context);
  if (vm.runInContext('Boolean(MAP_DATA.geophysics)', context)) {
    for (const mode of ['magnetic', 'gamma']) {
      vm.runInContext(`state.mode = '${mode}'; updateControls(); render()`, context);
      canvas.fire('click', target);
      assert.match(get('cellInfo').innerHTML, /Магнитная аномалия/);
      assert.match(get('cellInfo').innerHTML, /Гамма-фон/);
    }
  }
}

assert.equal(location.hash, '#truth');
assert.equal(get('truthPanel').classList.contains('hidden'), false);
assert.equal(get('similarityPanel').classList.contains('hidden'), true);
get('tab-truth').fire('keydown', {key: 'End'});
assert.equal(location.hash, '#similarity');
assert.equal(get('tab-similarity').attributes['aria-selected'], 'true');
assert.equal(get('truthPanel').classList.contains('hidden'), true);
assert.equal(get('similarityPanel').classList.contains('hidden'), false);
assert.match(html, /Сравнение с истинной картой/);
get('tab-preliminary').click();
assert.equal(location.hash, '#preliminary');
assert.equal(get('preliminaryPanel').classList.contains('hidden'), false);
assert.equal(get('expeditionPanel').classList.contains('hidden'), true);
assert.equal(get('preliminaryEmpty').classList.contains('hidden'), false);
assert.equal(get('preliminaryContent').classList.contains('hidden'), true);
assert.equal(get('preliminarySections').children.length, 0);
assert.equal(get('preliminaryTableBody').innerHTML, '');
assert.equal(get('geophysicalMap').innerHTML, '');
assert.equal(get('terrainSurveyMap').innerHTML, '');
assert.equal(get('outcropMap').innerHTML, '');
const surveySettings = preliminaryPlan?.methods ?? observations?.plan?.methods ?? {};
const geophysicalTables = ['magnetic_observations', 'gamma_observations'];
const hasMethod = key => Boolean(preliminaryPlan ? surveySettings[key] :
  geophysicalTables.includes(key) ? surveySettings.geophysical_survey?.enabled && observations.table_fields[key] :
  surveySettings[key]?.enabled);
const hasSurvey = [...geophysicalTables, 'terrain_survey', 'outcrops'].some(hasMethod);
assert.equal(get('collectPreliminary').classList.contains('hidden'), !hasSurvey);
if (hasSurvey) get('collectPreliminary').click();
assert.equal(get('preliminaryEmpty').classList.contains('hidden'), hasSurvey);
assert.equal(get('preliminaryContent').classList.contains('hidden'), !hasSurvey);
get('tab-expedition').click();
assert.equal(get('truthPanel').classList.contains('hidden'), true);
assert.equal(get('similarityPanel').classList.contains('hidden'), true);
assert.equal(get('preliminaryPanel').classList.contains('hidden'), true);
assert.equal(get('expeditionPanel').classList.contains('hidden'), false);
assert.equal(get('tab-expedition').attributes['aria-selected'], 'true');

if (!observations) {
  if (hasSurvey) assert.match(get('preliminaryTableBody').innerHTML, /(?:MAG|GAM|TER|OUT)-0001/);
  assert.equal(get('expeditionEmpty').classList.contains('hidden'), false);
  assert.equal(get('expeditionContent').classList.contains('hidden'), true);
  get('tab-recognized').click();
  assert.equal(get('recognizedPanel').classList.contains('hidden'), false);
  console.log('Empty expedition and workspace navigation: OK');
} else {
  assert.match(get('expeditionMetrics').innerHTML, new RegExp(String(observations.summary.hole_count)));
  assert.ok(!get('holeProfile').innerHTML.includes('NaN'));
  assert.match(get('holeProfile').innerHTML, /Вдоль ствола/);
  assert.ok(!get('holeTrajectory').innerHTML.includes('NaN'));
  const collars = observations.tables.borehole_collars;
  assert.equal(get('profileHole').value, collars[0]?.hole_id ?? '');
  for (const hole of collars) assert.ok(get('profileHole').innerHTML.includes(`value="${hole.hole_id}"`));
  const inclined = observations.tables.borehole_collars.find(hole => hole.dip_deg !== -90);
  if (inclined) {
    get('observationHoleFilter').value = inclined.hole_id;
    get('observationHoleFilter').fire('change');
    assert.equal(get('profileHole').value, inclined.hole_id);
    assert.match(get('surveyMap').innerHTML, new RegExp(`data-hole-trajectory="${inclined.hole_id}"`));
    assert.match(get('holeTrajectory').innerHTML, new RegExp(`data-borehole-path="${inclined.hole_id}"`));
    assert.match(get('holeProfileCaption').textContent, /угол.*азимут/);
    const depth = inclined.total_depth_m * Math.sin(-inclined.dip_deg * Math.PI / 180);
    assert.ok(get('holeTrajectoryCaption').textContent.includes(depth.toLocaleString('ru-RU', {maximumFractionDigits: 8})));
  }
  const lastHole = observations.tables.borehole_collars.at(-1).hole_id;
  get('profileHole').value = lastHole;
  get('profileHole').fire('change');
  assert.equal(get('observationHoleFilter').value, lastHole);
  assert.match(get('holeTrajectory').innerHTML, new RegExp(`data-borehole-path="${lastHole}"`));
  assert.ok(get('surveyMap').innerHTML.includes(`aria-pressed="true" data-hole="${lastHole}"`));
  assert.equal(get('observationCount').textContent, '1 записей');
  const drillingTargets = observations.drilling_targets || {};
  const placementKey = get('surveyPlacementKey');
  assert.equal(placementKey.classList.contains('hidden'), observations.plan.layout !== 'hybrid');
  const lastTarget = drillingTargets[lastHole];
  if (lastTarget) {
    const methodLabel = {magnetic: 'Магнитная аномалия', gamma: 'Повышенный гамма-фон'}[lastTarget.method];
    assert.equal(get('holeProfileTitle').textContent, `${lastHole} · ${methodLabel} · ${lastTarget.observation_id}`);
    assert.ok(placementKey.innerHTML.includes(methodLabel));
    assert.ok(get('surveyMap').innerHTML.includes(lastTarget.observation_id));
  } else {
    assert.equal(get('holeProfileTitle').textContent, lastHole);
  }
  const gammaRows = (observations.tables.downhole_gamma || []).filter(row => row.hole_id === lastHole);
  assert.equal(get('gammaProfilePanel').classList.contains('hidden'), !gammaRows.length);
  if (gammaRows.length) {
    assert.ok(get('gammaProfile').innerHTML.includes(gammaRows[0].measurement_id));
    assert.ok(!get('gammaProfile').innerHTML.includes('NaN'));
    const gammaTab = get('observationTabs').children.find(button => button.textContent === 'Гамма-каротаж');
    gammaTab.click();
    assert.match(get('observationTableHead').innerHTML, /gamma_count_rate_cps/);
    assert.equal(get('observationCount').textContent, `${gammaRows.length.toLocaleString('ru-RU')} записей`);
  }
  clickMapPoint('surveyMap', 'hole', collars[0].hole_id);
  assert.equal(get('profileHole').value, collars[0].hole_id);
  assert.equal(get('observationHoleFilter').value, collars[0].hole_id);
  assert.match(get('holeTrajectory').innerHTML, new RegExp(`data-borehole-path="${collars[0].hole_id}"`));
  const firstGamma = (observations.tables.downhole_gamma || []).find(row => row.hole_id === collars[0].hole_id);
  if (firstGamma) assert.ok(get('gammaProfile').innerHTML.includes(firstGamma.measurement_id));
  get('observationTabs').children[2].click();
  assert.match(get('observationTableHead').innerHTML, /Компонент/);
  assert.equal(get('analyteFilterLabel').classList.contains('hidden'), false);
  get('observationHoleFilter').value = '';
  get('observationHoleFilter').fire('change');
  if (observations.summary.assay_count > 50) {
    get('observationNext').click();
    assert.match(get('observationPageInfo').textContent, /^51/);
    get('observationPrevious').click();
    assert.match(get('observationPageInfo').textContent, /^1[–-]/);
  }
  get('observationAnalyteFilter').value = observations.plan.analytes[0].analyte;
  get('observationAnalyteFilter').fire('change');
  const matchingCount = observations.tables.borehole_assays.filter(row => row.analyte === observations.plan.analytes[0].analyte).length;
  assert.equal(get('observationCount').textContent, `${matchingCount.toLocaleString('ru-RU')} записей`);
  get('tab-recognized').click();
  assert.equal(get('recognizedPanel').classList.contains('hidden'), false);
  assert.equal(get('expeditionPanel').classList.contains('hidden'), true);
  get('tab-recognized').fire('keydown', {key: 'ArrowLeft'});
  assert.equal(get('expeditionPanel').classList.contains('hidden'), false);
  get('downloadObservations').click();
  get('downloadObservationCsv').click();
  const hasOutcrops = hasMethod('outcrops');
  const hasTerrainSurvey = hasMethod('terrain_survey');
  const geophysicalMethods = geophysicalTables.filter(hasMethod);
  const fieldMethods = get('expeditionSections').children.map(button => button.dataset.method);
  const surveyButtons = get('preliminarySections').children;
  assert.deepEqual(fieldMethods, ['boreholes', 'surface', 'trenches', 'structures', 'quality']);
  assert.deepEqual(surveyButtons.map(button => button.dataset.method),
    [...geophysicalMethods, hasTerrainSurvey && 'terrain_survey', hasOutcrops && 'outcrops'].filter(Boolean));
  assert.equal(get('preliminaryEmpty').classList.contains('hidden'), surveyButtons.length > 0);
  assert.equal(get('preliminaryContent').classList.contains('hidden'), surveyButtons.length === 0);
  get('expeditionSections').children[1].click();
  assert.equal(get('surfaceOverview').classList.contains('hidden'), false);
  assert.equal(get('boreholeOverview').classList.contains('hidden'), true);
  assert.ok(!get('surfaceMap').innerHTML.includes('NaN'));
  const surfaceSample = observations.tables.surface_geochemistry?.[0]?.sample_id;
  if (surfaceSample) {
    get('observationSampleFilter').value = surfaceSample;
    get('observationSampleFilter').fire('input');
    const count = observations.tables.surface_geochemistry.filter(row => row.sample_id === surfaceSample).length;
    assert.equal(get('observationCount').textContent, `${count} записей`);
    assert.equal(get('surfaceSampleSelect').value, surfaceSample);
    const lastSample = observations.tables.surface_geochemistry.at(-1).sample_id;
    get('surfaceSampleSelect').value = lastSample;
    get('surfaceSampleSelect').fire('change');
    assert.equal(get('observationSampleFilter').value, lastSample);
    assert.ok(get('surfaceSampleDetail').textContent.includes(lastSample));
    assert.ok(get('surfaceMap').innerHTML.includes(`aria-pressed="true" data-sample="${lastSample}"`));
    clickMapPoint('surfaceMap', 'sample', surfaceSample);
    assert.equal(get('surfaceSampleSelect').value, surfaceSample);
    get('surfaceSampleSelect').value = '';
    get('surfaceSampleSelect').fire('change');
    assert.equal(get('observationCount').textContent, `${observations.tables.surface_geochemistry.length.toLocaleString('ru-RU')} записей`);
  }
  get('downloadMethodGeoJson').click();
  get('expeditionSections').children[2].click();
  assert.equal(get('trenchOverview').classList.contains('hidden'), false);
  assert.equal(get('observationSampleFilter').value, '');
  assert.ok(!get('trenchProfile').innerHTML.includes('NaN'));
  if (observations.tables.trenches?.length) {
    const identifier = observations.tables.trenches.at(-1).trench_id;
    get('trenchSelect').value = identifier;
    get('trenchSelect').fire('change');
    assert.match(get('trenchCaption').textContent, new RegExp(identifier));
    assert.equal(get('observationTrenchFilter').value, identifier);
    const firstTrench = observations.tables.trenches[0].trench_id;
    get('observationTrenchFilter').value = firstTrench;
    get('observationTrenchFilter').fire('change');
    assert.equal(get('trenchSelect').value, firstTrench);
    clickMapPoint('trenchMap', 'trench', identifier);
    assert.equal(get('trenchSelect').value, identifier);
    get('observationTabs').children[2].click();
    assert.equal(get('analyteFilterLabel').classList.contains('hidden'), false);
  }
  get('downloadMethodGeoJson').click();
  get('expeditionSections').children[3].click();
  assert.equal(get('structureOverview').classList.contains('hidden'), false);
  assert.equal(get('observationTabs').children.length, 2);
  get('expeditionSections').children[4].click();
  assert.equal(get('qualityOverview').classList.contains('hidden'), false);
  get('observationQcFilter').value = 'fail';
  get('observationQcFilter').fire('change');
  const failCount = (observations.tables.quality_control || []).filter(row => row.qc_flag === 'fail').length;
  assert.equal(get('observationCount').textContent, `${failCount.toLocaleString('ru-RU')} записей`);
  const sourceDownloads = [];
  for (const source of observations.borehole_sources || []) {
    get('expeditionSections').children[0].click();
    get('observationSourceFilter').value = source.kind;
    get('observationSourceFilter').fire('change');
    assert.equal(get('profileSource').value, source.kind);
    assert.equal(get('observationCount').textContent, `${source.summary.hole_count.toLocaleString('ru-RU')} записей`);
    assert.equal(get('downloadDrillingSource').classList.contains('hidden'), false);
    assert.equal(get('downloadObservationCsv').textContent, 'CSV источника');
    const ids = new Set(source.hole_ids);
    for (const hole of observations.tables.borehole_collars) {
      if (!ids.has(hole.hole_id)) {
        assert.ok(!get('profileHole').innerHTML.includes(`value="${hole.hole_id}"`));
        assert.ok(!get('observationHoleFilter').innerHTML.includes(`value="${hole.hole_id}"`));
        assert.ok(!get('surveyMap').innerHTML.includes(`data-hole="${hole.hole_id}"`));
      }
    }
    assert.equal(get('profileHole').disabled, !source.hole_ids.length);
    if (!source.hole_ids.length) assert.equal(get('holeProfileTitle').textContent, 'В этом источнике нет скважин');
    const index = blobs.length;
    get('downloadDrillingSource').click();
    get('downloadObservationCsv').click();
    sourceDownloads.push({source, index});
    get('observationTabs').children[2].click();
    assert.equal(get('observationCount').textContent, `${source.summary.assay_count.toLocaleString('ru-RU')} записей`);
  }
  if (observations.borehole_sources?.length) {
    get('profileSource').value = '';
    get('profileSource').fire('change');
    assert.equal(get('observationSourceFilter').value, '');
    for (const hole of collars) assert.ok(get('profileHole').innerHTML.includes(`value="${hole.hole_id}"`));
  }
  get('expeditionSections').children[1].click();
  assert.equal(get('observationSourceFilter').value, '');
  assert.equal(get('sourceFilterLabel').classList.contains('hidden'), true);
  assert.equal(get('downloadDrillingSource').classList.contains('hidden'), true);
  assert.equal(get('downloadObservationCsv').textContent, 'CSV всей таблицы');
  const recognition = vm.runInContext('RECOGNITION_DATA', context);
  const recognitionDownload = blobs.length;
  get('tab-recognized').click();
  assert.equal(get('recognitionEmpty').classList.contains('hidden'), Boolean(recognition));
  if (recognition) {
    assert.equal(get('recognitionContent').classList.contains('hidden'), false);
    assert.ok(!get('recognitionMap').innerHTML.includes('NaN'));
    if (recognition.targets.length) {
      const target = recognition.targets[0];
      assert.ok(get('recognitionTargets').innerHTML.includes(target.site_id));
      if (target.terrain_context) assert.ok(get('recognitionTargets').innerHTML.includes(`data-terrain-observation="${target.terrain_context.observation_id}"`));
      assert.ok(get('recognitionMap').innerHTML.includes(`${target.analyte} · ${target.site_id}`));
      get('recognitionAnalyte').value = target.analyte;
      get('recognitionAnalyte').fire('change');
      const expected = recognition.targets.filter(row => row.analyte === target.analyte).length;
      assert.equal((get('recognitionTargets').innerHTML.match(/<tr>/g) || []).length, expected);
    } else {
      assert.match(get('recognitionTargets').innerHTML, /Нет целей/);
    }
    get('downloadRecognition').click();
  }
  const fieldTable = get('observationTableHead').innerHTML;
  get('tab-preliminary').click();
  const selectSurvey = name => surveyButtons.find(button => button.dataset.method === name).click();
  function checkPreliminarySelection(map, rows) {
    const filter = get('preliminaryPointFilter');
    assert.equal(filter.disabled, !rows.length);
    if (!rows.length) return;
    const last = rows.at(-1).observation_id;
    assert.ok(filter.innerHTML.includes(`value="${last}"`));
    filter.value = last;
    filter.fire('change');
    assert.equal(get('preliminaryCount').textContent, '1 записей');
    assert.ok(get('preliminaryTableBody').innerHTML.includes(last));
    assert.ok(get('preliminaryPointDetail').innerHTML.includes(last));
    assert.ok(get(map).innerHTML.includes(`aria-pressed="true" data-observation="${last}"`));
    const first = rows[0].observation_id;
    clickMapPoint(map, 'observation', first);
    assert.equal(filter.value, first);
    assert.ok(get('preliminaryTableBody').innerHTML.includes(first));
    filter.value = '';
    filter.fire('change');
    assert.equal(get('preliminaryCount').textContent, `${rows.length.toLocaleString('ru-RU')} записей`);
  }
  const outcropDownload = blobs.length;
  if (hasOutcrops) {
    selectSurvey('outcrops');
    assert.equal(get('outcropOverview').classList.contains('hidden'), false);
    const outcrops = observations.tables.outcrop_observations;
    assert.ok(!get('outcropMap').innerHTML.includes('NaN'));
    assert.equal((get('outcropMap').innerHTML.match(/<circle/g) || []).length, outcrops.length);
    checkPreliminarySelection('outcropMap', outcrops);
    get('downloadPreliminaryGeoJson').click();
  }
  const terrainDownload = blobs.length;
  if (hasTerrainSurvey) {
    selectSurvey('terrain_survey');
    assert.equal(get('terrainSurveyOverview').classList.contains('hidden'), false);
    const terrain = observations.tables.terrain_observations;
    assert.ok(!get('terrainSurveyMap').innerHTML.includes('NaN'));
    assert.equal((get('terrainSurveyMap').innerHTML.match(/<circle/g) || []).length, terrain.length);
    assert.match(get('preliminaryTableHead').innerHTML, /Тип рельефа/);
    checkPreliminarySelection('terrainSurveyMap', terrain);
    get('downloadPreliminaryGeoJson').click();
  }
  const geophysicalDownloads = [];
  for (const table of geophysicalMethods) {
    selectSurvey(table);
    assert.equal(get('geophysicalOverview').classList.contains('hidden'), false);
    const field = observations.tables[table];
    assert.equal((get('geophysicalMap').innerHTML.match(/<circle/g) || []).length, field.length);
    assert.ok(!get('geophysicalMap').innerHTML.includes('NaN'));
    const magnetic = table === 'magnetic_observations';
    if (field.length) assert.match(get('geophysicalMap').innerHTML, magnetic ? /нТл/ : /имп\/с/);
    assert.match(get('preliminaryTableHead').innerHTML, magnetic ? /magnetic_anomaly_nt/ : /gamma_count_rate_cps/);
    assert.doesNotMatch(get('preliminaryTableHead').innerHTML, magnetic ? /gamma_count_rate_cps/ : /magnetic_anomaly_nt/);
    checkPreliminarySelection('geophysicalMap', field);
    if (field.length > 50) {
      get('preliminaryNext').click();
      assert.match(get('preliminaryPageInfo').textContent, /^51/);
    }
    geophysicalDownloads.push({table, index: blobs.length, magnetic});
    get('downloadPreliminaryGeoJson').click();
    get('downloadPreliminaryCsv').click();
  }
  const preliminaryTable = get('preliminaryTableHead').innerHTML;
  get('tab-preliminary').fire('keydown', {key: 'ArrowRight'});
  assert.equal(location.hash, '#expedition');
  assert.equal(get('observationTableHead').innerHTML, fieldTable);
  get('tab-expedition').fire('keydown', {key: 'ArrowLeft'});
  assert.equal(location.hash, '#preliminary');
  assert.equal(get('preliminaryTableHead').innerHTML, preliminaryTable);
  Promise.all(blobs.map(blob => blob.text())).then(values => {
    const [json, csv, surfaceJson, trenchJson] = values;
    assert.equal(json, JSON.stringify(observations, null, 2));
    assert.equal(csv.split('\r\n').length, observations.tables.borehole_assays.length + 2);
    assert.match(csv, /^"campaign_id","sample_id","hole_id"/);
    assert.equal(JSON.parse(surfaceJson).features.length, observations.tables.surface_geochemistry.length);
    assert.equal(JSON.parse(trenchJson).features.length, observations.tables.trenches.length);
    if (recognition) assert.equal(values[recognitionDownload], JSON.stringify(recognition, null, 2));
    for (const [enabled, index, table] of [
      [hasOutcrops, outcropDownload, 'outcrop_observations'],
      [hasTerrainSurvey, terrainDownload, 'terrain_observations'],
    ]) {
      if (enabled) assert.deepEqual(JSON.parse(values[index]), JSON.parse(JSON.stringify(observations.geojson[table])));
    }
    for (const {table, index, magnetic} of geophysicalDownloads) {
      assert.deepEqual(JSON.parse(values[index]), JSON.parse(JSON.stringify(observations.geojson[table])));
      const surveyCsv = values[index + 1];
      const header = surveyCsv.split('\r\n')[0];
      assert.match(header, magnetic ? /"magnetic_anomaly_nt"/ : /"gamma_count_rate_cps"/);
      assert.doesNotMatch(header, magnetic ? /"gamma_count_rate_cps"/ : /"magnetic_anomaly_nt"/);
      assert.equal(surveyCsv.split('\r\n').length, observations.tables[table].length + 2);
    }
    for (const {source, index} of sourceDownloads) {
      const pack = JSON.parse(values[index]);
      assert.equal(pack.source.kind, source.kind);
      assert.equal(pack.data_kind, 'borehole_observation_source');
      for (const name of source.table_names) {
        const ids = new Set(source.hole_ids);
        const expected = observations.tables[name].filter(row => ids.has(row.hole_id));
        assert.equal(JSON.stringify(pack.tables[name]), JSON.stringify(expected));
      }
      assert.equal(values[index + 1].split('\r\n').length, source.summary.hole_count + 2);
      const path = require('node:path');
      const folder = path.dirname(process.argv[2] || 'output/map/map_view.html');
      const savedSource = path.join(folder, 'observations', source.directory, 'observations.json');
      if (fs.existsSync(savedSource)) {
        const saved = JSON.parse(fs.readFileSync(savedSource, 'utf8'));
        // The viewer upgrades legacy combined survey bundles to 1.7, but
        // leaves the archived source files and their original schema untouched.
        if (saved.schema_version === '1.6' && pack.schema_version === '1.7') {
          const archive = JSON.parse(fs.readFileSync(path.join(folder, 'observations', 'observations.json'), 'utf8'));
          assert.ok(archive.tables.geophysical_observations);
          saved.schema_version = '1.7';
        }
        assert.deepEqual(pack, saved);
      }
    }
    console.log('Expedition views, recognition map, filters and JSON/CSV/GeoJSON downloads: OK');
  }).catch(error => { console.error(error); process.exitCode = 1; });
}
