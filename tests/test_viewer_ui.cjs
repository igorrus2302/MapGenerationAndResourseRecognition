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
  getContext() { return {}; }
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

assert.equal(location.hash, '#truth');
assert.equal(get('truthPanel').classList.contains('hidden'), false);
get('tab-expedition').click();
assert.equal(get('truthPanel').classList.contains('hidden'), true);
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
  const lastHole = observations.tables.borehole_collars.at(-1).hole_id;
  get('observationHoleFilter').value = lastHole;
  get('observationHoleFilter').fire('change');
  assert.equal(get('holeProfileTitle').textContent, lastHole);
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
  assert.equal(get('expeditionSections').children.length, 5);
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
  Promise.all(blobs.map(blob => blob.text())).then(([json, csv, surfaceJson, trenchJson]) => {
    assert.equal(json, JSON.stringify(observations, null, 2));
    assert.equal(csv.split('\r\n').length, observations.tables.borehole_assays.length + 2);
    assert.match(csv, /^"campaign_id","sample_id","hole_id"/);
    assert.equal(JSON.parse(surfaceJson).features.length, observations.tables.surface_geochemistry.length);
    assert.equal(JSON.parse(trenchJson).features.length, observations.tables.trenches.length);
    console.log('Five expedition sections, navigation, filters, profiles, QA/QC and JSON/CSV/GeoJSON downloads: OK');
  }).catch(error => { console.error(error); process.exitCode = 1; });
}
