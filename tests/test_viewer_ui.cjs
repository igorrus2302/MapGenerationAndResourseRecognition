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
get('tab-expedition').click();
assert.equal(get('truthPanel').classList.contains('hidden'), true);
assert.equal(get('similarityPanel').classList.contains('hidden'), true);
assert.equal(get('expeditionPanel').classList.contains('hidden'), false);
assert.equal(get('tab-expedition').attributes['aria-selected'], 'true');

if (!observations) {
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
  const inclined = observations.tables.borehole_collars.find(hole => hole.dip_deg !== -90);
  if (inclined) {
    get('observationHoleFilter').value = inclined.hole_id;
    get('observationHoleFilter').fire('change');
    assert.match(get('surveyMap').innerHTML, new RegExp(`data-hole-trajectory="${inclined.hole_id}"`));
    assert.match(get('holeTrajectory').innerHTML, new RegExp(`data-borehole-path="${inclined.hole_id}"`));
    assert.match(get('holeProfileCaption').textContent, /угол.*азимут/);
    const depth = inclined.total_depth_m * Math.sin(-inclined.dip_deg * Math.PI / 180);
    assert.ok(get('holeTrajectoryCaption').textContent.includes(depth.toLocaleString('ru-RU', {maximumFractionDigits: 8})));
  }
  const lastHole = observations.tables.borehole_collars.at(-1).hole_id;
  get('observationHoleFilter').value = lastHole;
  get('observationHoleFilter').fire('change');
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
  const hasOutcrops = observations.plan.methods?.outcrops?.enabled;
  const hasTerrainSurvey = observations.plan.methods?.terrain_survey?.enabled;
  const hasGeophysics = observations.plan.methods?.geophysical_survey?.enabled;
  assert.equal(get('expeditionSections').children.length, 5 + Number(Boolean(hasOutcrops)) + Number(Boolean(hasTerrainSurvey)) + Number(Boolean(hasGeophysics)));
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
    assert.equal(get('observationCount').textContent, `${source.summary.hole_count.toLocaleString('ru-RU')} записей`);
    assert.equal(get('downloadDrillingSource').classList.contains('hidden'), false);
    assert.equal(get('downloadObservationCsv').textContent, 'CSV источника');
    const ids = new Set(source.hole_ids);
    for (const hole of observations.tables.borehole_collars) {
      if (!ids.has(hole.hole_id)) {
        assert.ok(!get('observationHoleFilter').innerHTML.includes(`value="${hole.hole_id}"`));
        assert.ok(!get('surveyMap').innerHTML.includes(`data-hole="${hole.hole_id}"`));
      }
    }
    if (!source.hole_ids.length) assert.equal(get('holeProfileTitle').textContent, 'В этом источнике нет скважин');
    const index = blobs.length;
    get('downloadDrillingSource').click();
    get('downloadObservationCsv').click();
    sourceDownloads.push({source, index});
    get('observationTabs').children[2].click();
    assert.equal(get('observationCount').textContent, `${source.summary.assay_count.toLocaleString('ru-RU')} записей`);
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
  const outcropDownload = blobs.length;
  if (hasOutcrops) {
    get('tab-expedition').click();
    get('expeditionSections').children[5].click();
    assert.equal(get('outcropOverview').classList.contains('hidden'), false);
    const outcrops = observations.tables.outcrop_observations;
    assert.ok(!get('outcropMap').innerHTML.includes('NaN'));
    assert.equal((get('outcropMap').innerHTML.match(/<circle/g) || []).length, outcrops.length);
    get('downloadMethodGeoJson').click();
  }
  const terrainDownload = blobs.length;
  if (hasTerrainSurvey) {
    get('tab-expedition').click();
    get('expeditionSections').children[5 + Number(Boolean(hasOutcrops))].click();
    assert.equal(get('terrainSurveyOverview').classList.contains('hidden'), false);
    const terrain = observations.tables.terrain_observations;
    assert.ok(!get('terrainSurveyMap').innerHTML.includes('NaN'));
    assert.equal((get('terrainSurveyMap').innerHTML.match(/<circle/g) || []).length, terrain.length);
    assert.match(get('observationTableHead').innerHTML, /Тип рельефа/);
    get('downloadMethodGeoJson').click();
  }
  const geophysicalDownload = blobs.length;
  if (hasGeophysics) {
    get('tab-expedition').click();
    get('expeditionSections').children.at(-1).click();
    assert.equal(get('geophysicalOverview').classList.contains('hidden'), false);
    const field = observations.tables.geophysical_observations;
    assert.equal((get('geophysicalMap').innerHTML.match(/<circle/g) || []).length, field.length);
    get('geophysicalChannel').value = 'gamma';
    get('geophysicalChannel').fire('change');
    assert.ok(!get('geophysicalMap').innerHTML.includes('NaN'));
    if (field.length) assert.match(get('geophysicalMap').innerHTML, /имп\/с/);
    get('downloadMethodGeoJson').click();
  }
  Promise.all(blobs.map(blob => blob.text())).then(values => {
    const [json, csv, surfaceJson, trenchJson] = values;
    assert.equal(json, JSON.stringify(observations, null, 2));
    assert.equal(csv.split('\r\n').length, observations.tables.borehole_assays.length + 2);
    assert.match(csv, /^"campaign_id","sample_id","hole_id"/);
    assert.equal(JSON.parse(surfaceJson).features.length, observations.tables.surface_geochemistry.length);
    assert.equal(JSON.parse(trenchJson).features.length, observations.tables.trenches.length);
    if (recognition) assert.equal(values[recognitionDownload], JSON.stringify(recognition, null, 2));
    if (hasOutcrops) assert.equal(JSON.parse(values[outcropDownload]).features.length, observations.summary.outcrop_count);
    if (hasTerrainSurvey) assert.equal(JSON.parse(values[terrainDownload]).features.length, observations.summary.terrain_observation_count);
    if (hasGeophysics) assert.equal(JSON.parse(values[geophysicalDownload]).features.length, observations.summary.geophysical_observation_count);
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
      if (fs.existsSync(savedSource)) assert.deepEqual(pack, JSON.parse(fs.readFileSync(savedSource, 'utf8')));
    }
    console.log('Expedition views, recognition map, filters and JSON/CSV/GeoJSON downloads: OK');
  }).catch(error => { console.error(error); process.exitCode = 1; });
}
