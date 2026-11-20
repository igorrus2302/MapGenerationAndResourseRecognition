"""Offline workspace tabs and views that render only public expedition records."""

from .expedition_methods_view import METHODS_HTML, METHODS_SCRIPT, METHODS_STYLES

WORKSPACE_STYLES = r'''
    .workspace-tabs { height: 62px; display: flex; align-items: stretch; gap: 5px; padding: 8px 22px 0; background: white; border-bottom: 1px solid var(--line); }
    .workspace-tab { width: auto; border: 0; border-bottom: 3px solid transparent; border-radius: 8px 8px 0 0; display: flex; align-items: center; gap: 10px; padding: 10px 20px; color: var(--muted); background: transparent; }
    .workspace-tab[aria-selected="true"] { color: var(--blue); border-bottom-color: var(--blue); background: #eef7fb; }
    .tab-number { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 7px; background: #edf1f6; font-size: 11px; }
    .workspace-tab[aria-selected="true"] .tab-number { background: #d1eaf4; }
    .layout { height: calc(100dvh - 132px); }
    .workspace-page { height: calc(100dvh - 132px); overflow: auto; padding: 26px; }
    .expedition-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
    .expedition-heading h2 { margin: 0 0 4px; font-size: 23px; color: var(--navy); }
    .expedition-heading p { margin: 0; color: var(--muted); }
    .primary-button { width: auto; padding: 10px 16px; color: white; background: var(--blue); border-color: var(--blue); white-space: nowrap; }
    .primary-button:hover { color: white; background: #12658f; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
    .metric-card { background: white; border: 1px solid var(--line); padding: 14px 18px; border-radius: 12px; }
    .metric-card strong { display: block; font-size: 25px; color: var(--navy); }
    .metric-card span { color: var(--muted); font-size: 12px; }
    .expedition-grid { display: grid; grid-template-columns: minmax(280px, .9fr) minmax(400px, 1.5fr); gap: 18px; align-items: stretch; margin-bottom: 18px; }
    .panel-card { background: white; border: 1px solid var(--line); border-radius: 13px; padding: 18px; min-width: 0; }
    .panel-card h3 { margin: 0 0 4px; font-size: 15px; color: var(--navy); }
    .muted { color: var(--muted); font-size: 12px; }
    .survey-map { width: 100%; display: block; height: 275px; }
    .hole-dot { cursor: pointer; }
    .hole-dot:focus { outline: none; stroke: var(--orange); stroke-width: 3; }
    .hole-dot:hover { stroke: var(--orange); stroke-width: 3; }
    .profile-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
    .profile-heading select { width: auto; max-width: 180px; }
    .hole-profile { height: 280px; width: 100%; display: block; }
    .hole-trajectory { height: 190px; width: 100%; display: block; margin-top: 16px; }
    .profile-key { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: var(--muted); margin-top: 8px; }
    .profile-key span { display: inline-flex; align-items: center; gap: 5px; }
    .profile-key i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
    .data-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .data-heading button { width: auto; }
    .data-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0; }
    .data-tab { width: auto; min-height: 34px; font-size: 12px; }
    .data-tab[aria-pressed="true"] { color: var(--blue); background: #eaf5fa; border-color: #a5ccdf; }
    .data-filters { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; margin-bottom: 12px; }
    .data-filters label { margin: 0; min-width: 155px; }
    .data-filters select { display: block; margin-top: 5px; font-size: 12px; }
    .table-scroll { overflow: auto; max-height: 380px; border: 1px solid var(--line); border-radius: 8px; }
    .observation-table { border-collapse: collapse; width: 100%; font-size: 12px; white-space: nowrap; }
    .observation-table th { background: #f0f5f9; color: #486581; font-weight: 600; position: sticky; top: 0; z-index: 1; }
    .observation-table th, .observation-table td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #e8edf2; }
    .observation-table tbody tr:hover { background: #f4fafc; }
    .table-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; font-size: 12px; color: var(--muted); }
    .page-buttons { display: flex; gap: 6px; }
    .page-buttons button { width: auto; min-height: 32px; font-size: 12px; }
    button:disabled { opacity: .4; cursor: default; }
    .method-notes { margin-top: 18px; color: var(--muted); font-size: 12px; line-height: 1.65; }
    .method-notes summary { cursor: pointer; color: var(--navy); font-weight: 600; }
    .method-notes ul { padding-left: 20px; margin-bottom: 0; }
    .empty-card { width: min(540px, 100%); padding: 36px; background: white; border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 12px 40px #102a4308; }
    .empty-card h2 { font-size: 24px; color: var(--navy); margin: 18px 0 10px; }
    .empty-card p { color: var(--muted); line-height: 1.7; }
    @media (max-width: 1000px) {
      .expedition-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 860px) {
      .layout { height: auto; }
      .workspace-tabs { padding-left: 6px; padding-right: 6px; gap: 0; height: auto; min-height: 56px; }
      .workspace-tab { font-size: 11px; padding: 9px 8px; flex: 1; justify-content: center; gap: 5px; }
      .tab-number { display: none; }
      .workspace-page { height: auto; min-height: calc(100dvh - 140px); padding: 16px; overflow: visible; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .expedition-heading { align-items: flex-start; flex-direction: column; }
      .table-footer { align-items: flex-start; flex-direction: column; }
    }
'''

WORKSPACE_TABS = r'''
  <nav class="workspace-tabs" role="tablist" aria-label="Этапы исследования">
    <button class="workspace-tab" id="tab-truth" role="tab" aria-controls="truthPanel" aria-selected="true" data-workspace="truth"><span class="tab-number">01</span>Истинная карта</button>
    <button class="workspace-tab" id="tab-expedition" role="tab" aria-controls="expeditionPanel" aria-selected="false" tabindex="-1" data-workspace="expedition"><span class="tab-number">02</span>Разведочная экспедиция</button>
    <button class="workspace-tab" id="tab-recognized" role="tab" aria-controls="recognizedPanel" aria-selected="false" tabindex="-1" data-workspace="recognized"><span class="tab-number">03</span>Распознанная карта</button>
  </nav>
'''

EXPEDITION_PANEL = r'''
  <section id="expeditionPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-expedition">
    <div id="expeditionEmpty" class="empty-card hidden"><h2>Экспедиция ещё не создана</h2><p>Наблюдения появятся после генерации разведочной экспедиции.</p></div>
    <div id="expeditionContent">
      <div class="expedition-heading">
        <div><h2 id="expeditionTitle"></h2><p id="expeditionSubtitle"></p></div>
        <button id="downloadObservations" class="primary-button">Скачать все наблюдения · JSON</button>
      </div>
      <div class="metric-grid" id="expeditionMetrics"></div>
      <div class="method-sections" id="expeditionSections" aria-label="Виды разведочных наблюдений"></div>
      <div class="expedition-grid" id="boreholeOverview">
        <div class="panel-card">
          <h3>План бурения</h3><div class="muted">Нажмите на скважину, чтобы открыть её данные</div>
          <svg id="surveyMap" class="survey-map" viewBox="0 0 520 300" role="group" aria-label="Положения наблюдённых скважин"></svg>
          <div class="muted" id="surveyCaption"></div>
        </div>
        <div class="panel-card">
          <div class="profile-heading"><div><h3 id="holeProfileTitle"></h3><div id="holeProfileCaption" class="muted"></div></div><select id="profileAnalyte" aria-label="Компонент на графике содержания"></select></div>
          <svg id="holeProfile" class="hole-profile" viewBox="0 0 700 300" role="img" aria-label="Литологический журнал и анализы выбранной скважины"></svg>
          <div class="profile-key" id="profileKey"></div>
          <svg id="holeTrajectory" class="hole-trajectory" viewBox="0 0 700 200" role="img" aria-label="Траектория выбранной скважины в вертикальной плоскости"></svg>
          <div class="muted" id="holeTrajectoryCaption"></div>
        </div>
      </div>
      __METHOD_OVERVIEWS__
      <div class="panel-card">
        <div class="data-heading"><div><h3 id="dataSectionTitle">Данные экспедиции</h3><div class="muted">Наблюдения и измерения выбранного раздела</div></div><div class="data-downloads"><button id="downloadMethodGeoJson" class="hidden">Скачать GeoJSON</button><button id="downloadDrillingSource" class="hidden">Скачать источник · JSON</button><button id="downloadObservationCsv">CSV всей таблицы</button></div></div>
        <div class="data-tabs" id="observationTabs"></div>
        <div class="data-filters">
          <label id="sourceFilterLabel">Источник бурения<select id="observationSourceFilter"></select></label>
          <label id="holeFilterLabel">Скважина<select id="observationHoleFilter"></select></label>
          <label id="trenchFilterLabel" class="hidden">Траншея<select id="observationTrenchFilter"></select></label>
          <label id="analyteFilterLabel">Компонент<select id="observationAnalyteFilter"></select></label>
          <label id="sampleFilterLabel" class="hidden">Проба<input id="observationSampleFilter" type="text" placeholder="Все пробы"></label>
          <label id="qcFilterLabel" class="hidden">Результат контроля<select id="observationQcFilter"><option value="">Все результаты</option><option value="pass">В пределах допуска</option><option value="warning">Предупреждение</option><option value="fail">Вне допуска</option><option value="not_checked">Не оценено</option></select></label>
          <span id="observationCount" class="muted" aria-live="polite"></span>
        </div>
        <div class="table-scroll"><table class="observation-table"><thead id="observationTableHead"></thead><tbody id="observationTableBody"></tbody></table></div>
        <div class="table-footer"><span id="observationPageInfo" aria-live="polite"></span><div class="page-buttons"><button id="observationPrevious">← Назад</button><button id="observationNext">Далее →</button></div></div>
      </div>
      <details class="method-notes"><summary>План экспедиции и допущения модели</summary><div id="expeditionPlan"></div><ul id="expeditionNotes"></ul></details>
    </div>
  </section>
  <section id="recognizedPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-recognized">
    <div class="empty-card" id="recognitionEmpty"><h2>Поиск по наблюдениям</h2><p>Результаты поиска ещё не загружены.</p></div>
    <div id="recognitionContent" class="hidden">
      <div class="expedition-heading">
        <div><h2>Результаты поиска</h2><p id="recognitionSummary"></p></div>
        <button id="downloadRecognition" class="primary-button">Скачать результаты · JSON</button>
      </div>
      <div class="expedition-grid">
        <div class="panel-card">
          <div class="profile-heading"><h3>Карта наблюдений и целей поиска</h3><select id="recognitionAnalyte" aria-label="Компонент на карте поиска"><option value="">Все компоненты</option></select></div>
          <svg id="recognitionMap" class="survey-map" viewBox="0 0 520 300" role="img" aria-label="План участка и положения выделенных целей"></svg>
          <div class="muted">Синие линии — бурение и траншеи, серые точки — почвенные пробы, оранжевые метки — выделенные интервалы, зелёные — почвенные аномалии, фиолетовые — геофизические аномалии.</div>
        </div>
        <div class="panel-card">
          <h3>Пробы и признаки</h3>
          <div class="table-scroll"><table class="observation-table"><thead><tr><th scope="col">Источник</th><th scope="col">Глубина, м</th><th scope="col">Пик / порог</th><th scope="col">Поддержка</th></tr></thead><tbody id="recognitionTargets"></tbody></table></div>
        </div>
      </div>
    </div>
  </section>
'''

WORKSPACE_SCRIPT = r'''
    (() => {
      const tabs = [...document.querySelectorAll('.workspace-tab')];
      const panels = {truth: 'truthPanel', expedition: 'expeditionPanel', recognized: 'recognizedPanel'};
      const truthStats = document.getElementById('headerStats').innerHTML;
      function activate(name) {
        if (!panels[name]) name = 'truth';
        for (const [key, id] of Object.entries(panels)) document.getElementById(id).classList.toggle('hidden', key !== name);
        for (const tab of tabs) {
          const selected = tab.dataset.workspace === name;
          tab.setAttribute('aria-selected', String(selected));
          tab.tabIndex = selected ? 0 : -1;
        }
        if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
        document.getElementById('headerStats').innerHTML = name === 'truth' ? truthStats : name === 'expedition' && OBSERVATION_DATA
          ? `<span>${OBSERVATION_DATA.summary.hole_count} скважин</span><span>${OBSERVATION_DATA.summary.total_sample_count ?? OBSERVATION_DATA.summary.sample_count} полевых проб</span>`
          : '<span>Поиск по наблюдениям</span>';
        if (name === 'truth') requestAnimationFrame(resizeCanvas);
      }
      for (const button of document.querySelectorAll('[data-workspace]')) button.addEventListener('click', () => activate(button.dataset.workspace));
      tabs.forEach((tab, index) => tab.addEventListener('keydown', event => {
        const next = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1}[event.key];
        if (next === undefined) return;
        event.preventDefault(); tabs[next].focus(); activate(tabs[next].dataset.workspace);
      }));
      window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
      activate(location.hash.slice(1));
    })();

    // This view receives the public bundle only. All profiles and tables use its records.
    ((observations) => {
      if (!observations) {
        document.getElementById('expeditionEmpty').classList.remove('hidden');
        document.getElementById('expeditionContent').classList.add('hidden');
        return;
      }
      const element = id => document.getElementById(id);
      const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
      const number = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 8});
      const tableNames = {borehole_collars: 'Скважины', borehole_lithology: 'Литология', borehole_assays: 'Анализы проб', downhole_properties: 'Физические свойства', structural_observations: 'Контакты и разломы', fault_intersections: 'Интервалы нарушений', surface_geochemistry: 'Почвенные пробы', trenches: 'Положение траншей', trench_intervals: 'Описание дна', trench_samples: 'Канавные пробы', quality_control: 'Контрольные пробы'};
      const fieldNames = {
        campaign_id: 'Экспедиция', hole_id: 'Скважина', x_m: 'X, м', y_m: 'Y, м', collar_elevation_m: 'Отметка устья, м',
        total_depth_m: 'Длина ствола, м', azimuth_deg: 'Азимут, °', dip_deg: 'Угол от горизонтали, °', coordinate_system: 'Система координат',
        position_uncertainty_m: 'Погрешность положения, м', drilling_method: 'Способ бурения', start_date: 'Начало', end_date: 'Окончание', hole_status: 'Состояние',
        interval_id: 'Интервал', from_m: 'От, м', to_m: 'До, м', observed_rock_id: 'Код породы', observed_rock_name: 'Порода', description: 'Описание',
        weathering: 'Выветрелость', alteration: 'Изменения', confidence: 'Уверенность', observer: 'Наблюдатель', logged_date: 'Дата описания',
        sample_id: 'Проба', analyte: 'Компонент', result_value: 'Результат', result_qualifier: 'Квалификатор', unit: 'Единица', detection_limit: 'Предел обнаружения',
        analysis_method: 'Метод анализа', laboratory: 'Лаборатория', certificate_id: 'Сертификат', qc_type: 'Тип пробы', qc_flag: 'Контроль качества',
        measurement_id: 'Измерение', depth_m: 'Вдоль ствола, м', density_g_cm3: 'Плотность, г/см³', porosity_percent: 'Пористость, %', measurement_method: 'Метод измерения',
        density_error_g_cm3: 'Погрешность плотности', porosity_error_percent: 'Погрешность пористости', observation_id: 'Наблюдение', feature_type: 'Тип структуры',
        strike_deg: 'Простирание, °', dip_direction_deg: 'Направление падения, °', offset_estimate_m: 'Оценка смещения, м', observation_method: 'Метод наблюдения', notes: 'Примечания'
      };
      const categoryNames = {completed: 'Завершена', medium: 'Средняя', high: 'Высокая', low: 'Низкая', contact: 'Контакт', primary: 'Первичная', not_checked: 'Не проверено', core_logging: 'Описание керна', synthetic_core: 'Синтетическое бурение', synthetic_core_measurement: 'Синтетическое измерение', synthetic_assay: 'Синтетический анализ', local_cartesian: 'Локальная, м', lt: 'Ниже предела'};
      const tables = observations.tables;
      const holes = tables.borehole_collars;
      const drillingSources = observations.borehole_sources || [];
      const sourceByKind = new Map(drillingSources.map(source => [source.kind, source]));
      const rocks = Object.fromEntries(observations.rock_catalog.map(rock => [rock.id, rock]));
      let selectedHole = holes[0]?.hole_id;
      let activeTable = 'borehole_collars';
      let page = 0;
      const pageSize = 50;
      const summary = observations.summary;
      element('expeditionTitle').textContent = observations.campaign.title;
      element('expeditionSubtitle').textContent = `${observations.campaign.campaign_id} · ${observations.campaign.date} · комплекс разведочных наблюдений`;
      element('expeditionMetrics').innerHTML = [[summary.hole_count, 'скважин'], [`${number(summary.drilled_m)} м`, 'пройдено бурением'], [number(summary.total_sample_count ?? summary.sample_count), 'полевых проб всех методов'], [number(summary.total_assay_count ?? summary.assay_count), 'результатов полевых проб']].map(([value, label]) => `<div class="metric-card"><strong>${escape(value)}</strong><span>${label}</span></div>`).join('');
      const options = holes.map(hole => `<option value="${escape(hole.hole_id)}">${escape(hole.hole_id)}</option>`).join('');
      element('observationHoleFilter').innerHTML = '<option value="">Все скважины</option>' + options;
      element('observationSourceFilter').innerHTML = '<option value="">Все источники бурения</option>' + drillingSources.map(source => `<option value="${escape(source.kind)}">${escape(source.title)} · ${source.summary.hole_count} скв.</option>`).join('');
      const analyteOptions = observations.plan.analytes.map(item => `<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');
      element('profileAnalyte').innerHTML = analyteOptions;
      const filterAnalytes = [...new Map([...observations.plan.analytes, ...(observations.plan.methods?.surface_geochemistry?.analytes || [])].map(item => [item.analyte, item])).values()];
      element('observationAnalyteFilter').innerHTML = '<option value="">Все компоненты</option>' + filterAnalytes.map(item => `<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');
      element('expeditionNotes').innerHTML = observations.notes.map(note => `<li>${escape(note)}</li>`).join('');
      const layout = {grid: 'регулярная сетка', random: 'случайные точки', manual: 'ручной план'}[observations.plan.layout];
      element('expeditionPlan').textContent = `Размещение скважин: ${layout}. Интервал скважинных проб: ${number(observations.plan.sample_length_m)} м. Всего пропущено проб: ${summary.total_missing_sample_count ?? summary.missing_sample_count}. Режим: ${observations.plan.ideal ? 'идеальные наблюдения' : 'с погрешностями'}. Параметры экспедиции задаются при генерации.`;

      function download(content, filename, type) {
        const url = URL.createObjectURL(new Blob([content], {type}));
        const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      element('downloadObservations').addEventListener('click', () => download(JSON.stringify(observations, null, 2), 'observations.json', 'application/json'));
      element('downloadObservationCsv').addEventListener('click', () => {
        const fields = observations.table_fields[activeTable];
        const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
        const source = sourceByKind.get(element('observationSourceFilter').value);
        const rows = [fields, ...sourceRows(activeTable).map(row => fields.map(field => row[field]))];
        download(rows.map(row => row.map(quote).join(',')).join('\r\n') + '\r\n', `${source ? source.kind + '_' : ''}${activeTable}.csv`, 'text/csv;charset=utf-8');
      });
      function sourceRows(name) {
        const source = sourceByKind.get(element('observationSourceFilter').value);
        if (!source || !observations.table_fields[name]?.includes('hole_id')) return tables[name] || [];
        const ids = new Set(source.hole_ids);
        return (tables[name] || []).filter(row => ids.has(row.hole_id));
      }
      function updateSourceHoles() {
        const available = sourceRows('borehole_collars');
        element('observationHoleFilter').innerHTML = '<option value="">Все скважины источника</option>' + available.map(hole => `<option value="${escape(hole.hole_id)}">${escape(hole.hole_id)}</option>`).join('');
        if (!available.some(hole => hole.hole_id === selectedHole)) selectedHole = available[0]?.hole_id;
        drawSurvey(); drawProfile();
      }
      element('observationSourceFilter').addEventListener('change', () => {
        page = 0; updateSourceHoles(); renderTable();
      });
      element('downloadDrillingSource').addEventListener('click', () => {
        const source = sourceByKind.get(element('observationSourceFilter').value);
        if (!source) return;
        const sourceTables = Object.fromEntries(source.table_names.map(name => [name, sourceRows(name)]));
        const rockIds = new Set(sourceTables.borehole_lithology.map(row => row.observed_rock_id));
        const bundle = {schema_version: observations.schema_version, data_kind: 'borehole_observation_source',
          source, campaign: observations.campaign, plan: observations.plan, summary: source.summary, notes: observations.notes,
          rock_catalog: observations.rock_catalog.filter(rock => rockIds.has(rock.id)),
          table_fields: Object.fromEntries(source.table_names.map(name => [name, observations.table_fields[name]])), tables: sourceTables};
        download(JSON.stringify(bundle, null, 2), `${source.kind}.json`, 'application/json');
      });

      function drawSurvey() {
        const width = observations.campaign.width_m, height = observations.campaign.height_m;
        const scale = Math.min(435 / width, 235 / height);
        const w = width * scale, h = height * scale;
        const left = (520 - w) / 2, top = 18;
        let markup = `<rect x="${left}" y="${top}" width="${w}" height="${h}" rx="4" fill="#f0f6f8" stroke="#b7ccd8"/>`;
        for (let index = 1; index < 5; index++) {
          markup += `<path d="M ${left + w * index / 5} ${top} v ${h} M ${left} ${top + h * index / 5} h ${w}" stroke="#dce7ed" stroke-dasharray="3 4"/>`;
        }
        markup += `<text x="${left}" y="${top + h + 19}" font-size="11" fill="#627d98">0</text><text x="${left + w}" y="${top + h + 19}" text-anchor="end" font-size="11" fill="#627d98">X · ${number(width)} м</text><text x="${left}" y="${top - 6}" font-size="10" fill="#627d98">Y · ${number(height)} м</text>`;
        for (const hole of sourceRows('borehole_collars')) {
          const cx = left + hole.x_m * scale, cy = top + h - hole.y_m * scale;
          const end = holePosition(hole, hole.total_depth_m);
          const ex = left + end.x * scale, ey = top + h - end.y * scale;
          const selected = hole.hole_id === selectedHole;
          const color = selected ? '#e95e2a' : '#1677a8';
          if (hole.dip_deg !== -90) markup += `<line class="hole-dot" data-hole="${escape(hole.hole_id)}" data-hole-trajectory="${escape(hole.hole_id)}" x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="${color}" stroke-width="${selected ? 4 : 2}" opacity="${selected ? 1 : .55}"><title>${escape(hole.hole_id)} · проекция ствола</title></line><circle cx="${ex}" cy="${ey}" r="3" fill="${color}"/>`;
          markup += `<circle class="hole-dot" role="button" tabindex="0" aria-label="${escape(hole.hole_id)}" aria-pressed="${selected}" data-hole="${escape(hole.hole_id)}" cx="${cx}" cy="${cy}" r="${selected ? 7 : 5}" fill="${color}" stroke="white" stroke-width="2"><title>${escape(hole.hole_id)} · ствол ${number(hole.total_depth_m)} м · угол ${number(hole.dip_deg)}° · азимут ${number(hole.azimuth_deg)}°</title></circle>`;
        }
        element('surveyMap').innerHTML = markup;
        element('surveyCaption').textContent = `Участок ${number(width)} × ${number(height)} м · крупные точки — устья, линии — проекции наклонных стволов, малые точки — забои`;
      }
      function holePosition(hole, distance) {
        const azimuth = (hole.azimuth_deg ?? 0) * Math.PI / 180;
        const dip = (hole.dip_deg ?? -90) * Math.PI / 180;
        const horizontal = hole.dip_deg === -90 ? 0 : distance * Math.cos(dip);
        return {x: hole.x_m + horizontal * Math.sin(azimuth), y: hole.y_m + horizontal * Math.cos(azimuth), depth: -distance * Math.sin(dip), horizontal};
      }
      function renderRecognition(result) {
        if (!result) return;
        element('recognitionEmpty').classList.add('hidden');
        element('recognitionContent').classList.remove('hidden');
        const {targets, summary: searchSummary, campaign} = result;
        const {width_m: width, height_m: height} = campaign;
        const scale = Math.min(435 / width, 235 / height);
        const left = (520 - width * scale) / 2, top = 20, bottom = top + height * scale;
        const x = value => left + value * scale;
        const y = value => bottom - value * scale;
        const line = (a, b, color, thickness) => `<line x1="${x(a[0])}" y1="${y(a[1])}" x2="${x(b[0])}" y2="${y(b[1])}" stroke="${color}" stroke-width="${thickness}" stroke-linecap="round"/>`;
        const dot = (a, color, size, title) => `<circle cx="${x(a[0])}" cy="${y(a[1])}" r="${size}" fill="${color}"><title>${escape(title)}</title></circle>`;
        let plan = `<rect x="${left}" y="${top}" width="${width * scale}" height="${height * scale}" rx="4" fill="#f0f6f8" stroke="#b7ccd8"/>`;
        plan += `<text x="${left}" y="${top - 6}" font-size="11" fill="#486581">Y · ${number(height)} м</text><text x="${x(width)}" y="${bottom + 18}" text-anchor="end" font-size="11" fill="#486581">X · ${number(width)} м</text>`;
        for (const row of new Map((tables.surface_geochemistry || []).map(row => [row.sample_id, row])).values()) {
          plan += dot([row.x_m, row.y_m], '#9caebc', 2, row.sample_id);
        }
        for (const hole of holes) {
          const end = holePosition(hole, hole.total_depth_m);
          plan += line([hole.x_m, hole.y_m], [end.x, end.y], '#76a8bd', 1.5) + dot([hole.x_m, hole.y_m], '#458eab', 3, hole.hole_id);
        }
        for (const trench of tables.trenches || []) {
          plan += line([trench.start_x_m, trench.start_y_m], [trench.end_x_m, trench.end_y_m], '#458eab', 2);
        }
        for (const anomaly of result.geophysical_anomalies || []) {
          const channel = geophysicalChannels[anomaly.method];
          plan += dot([anomaly.x_m, anomaly.y_m], '#9354b5', 3, `${anomaly.observation_id} · ${channel.label} · ${number(anomaly.deviation)} ${channel.unit} от фона`);
        }

        element('recognitionSummary').textContent = targets.length
          ? `Минерализованных интервалов — ${number(searchSummary.mineralized_intervals)} · почвенных аномалий — ${number(searchSummary.soil_anomalies)}`
          : 'Ни один результат не прошёл поисковые пороги. Участок обследован по отдельным траекториям и точкам отбора проб.';
        if (searchSummary.geophysical_anomaly_count) element('recognitionSummary').textContent += ` · Геофизических аномалий — ${number(searchSummary.geophysical_anomaly_count)}`;
        const analyte = element('recognitionAnalyte');
        analyte.innerHTML = '<option value="">Все компоненты</option>' + [...new Set(targets.map(target => target.analyte))].sort()
          .map(name => `<option value="${escape(name)}">${escape(name)}</option>`).join('');
        const signalNames = {
          host_rock: 'Вмещающая порода', observed_fault: 'Разлом', steep_fault: 'Крутое падение разлома',
          observed_contact: 'Контакт пород', intrusive_rock: 'Порода интрузии', compatible_core_properties: 'Плотность и пористость согласуются',
          adjacent_positive_samples: 'Смежные пробы', nearby_soil_anomaly: 'Аномалия рядом',
          terrain_bauxite_depression: 'Понижение над карбонатным контактом', terrain_exposed_host: 'Рядом выход подходящей породы',
          geophysics_magnetic: 'Магнитное подтверждение', geophysics_gamma: 'Гамма-аномалия у поверхности'
        };
        function renderTargets() {
          const shown = targets.filter(target => !analyte.value || target.analyte === analyte.value);
          element('recognitionMap').innerHTML = plan + shown.map(target => {
            const color = target.kind === 'soil_anomaly' ? '#168c86' : '#e95e2a';
            const interval = target.start_xyz_m ? line(target.start_xyz_m, target.end_xyz_m, color, 4) : '';
            return interval + dot(target.center_xyz_m, color, 5, `${target.analyte} · ${target.site_id}`);
          }).join('');
          element('recognitionTargets').innerHTML = shown.map(target => {
            const depths = target.start_xyz_m ? `${number(target.start_xyz_m[2])}–${number(target.end_xyz_m[2])}` : '—';
            const signals = target.supporting_signals.map(signal => signalNames[signal]);
            if (target.geology?.core_properties?.conflicting_length_m > 0) signals.push('Есть расхождения со свойствами пород');
            if (target.qc_warning_sample_ids.length || Object.keys(target.laboratory_alerts).length) signals.push('Есть замечания QA/QC');
            const context = target.terrain_context;
            const terrain = context ? `<div class="muted" data-terrain-observation="${escape(context.observation_id)}">Рельеф · ${escape(terrainTypes[context.terrain_type]?.label || context.terrain_type)} · ${escape(context.observation_id)}</div>` : '';
            const outcrop = context?.outcrop ? `<div class="muted">Обнажение · ${escape(context.outcrop.observation_id)} · ${number(context.outcrop.distance_xy_m)} м</div>` : '';
            const field = target.geophysical_evidence;
            const geophysics = field ? `<div class="muted">Геофизика · ${escape(field.observation_id)} · ${number(field.distance_xy_m)} м</div>` : '';
            return `<tr><td>${escape(target.site_id)} · ${escape(target.analyte)}</td><td>${depths}</td><td>${number(target.peak_result)} / ${number(target.threshold)} ${escape(target.unit)}</td><td>${signals.join(', ') || '—'}${terrain}${outcrop}${geophysics}</td></tr>`;
          }).join('') || '<tr><td colspan="4">Нет целей по выбранным наблюдениям</td></tr>';
        }
        analyte.addEventListener('change', renderTargets);
        element('downloadRecognition').addEventListener('click', () => download(JSON.stringify(result, null, 2), 'recognition.json', 'application/json'));
        renderTargets();
      }
      function drawTrajectory(hole) {
        const end = holePosition(hole, hole.total_depth_m);
        const scale = Math.min(480 / Math.max(1, end.horizontal), 135 / Math.max(1, end.depth));
        const x = 110 + end.horizontal * scale, y = 24 + end.depth * scale;
        element('holeTrajectory').innerHTML = `<text x="18" y="14" font-size="12" fill="#486581">Вертикальная глубина</text><path d="M 110 24 V 164 H 630" fill="none" stroke="#b7ccd8"/><path d="M 110 24 V ${y} H ${x}" fill="none" stroke="#b7ccd8" stroke-dasharray="4 4"/><path data-borehole-path="${escape(hole.hole_id)}" d="M 110 24 L ${x} ${y}" fill="none" stroke="#e95e2a" stroke-width="4"/><circle cx="110" cy="24" r="4" fill="#1677a8"/><circle cx="${x}" cy="${y}" r="4" fill="#e95e2a"/><text x="98" y="${y + 4}" text-anchor="end" font-size="11" fill="#486581">${number(end.depth)} м</text><text x="${x}" y="181" text-anchor="middle" font-size="11" fill="#486581">${number(end.horizontal)} м</text><text x="630" y="197" text-anchor="end" font-size="11" fill="#627d98">Горизонтальное отклонение от устья</text>`;
        element('holeTrajectoryCaption').textContent = `Забой: X ${number(end.x)} · Y ${number(end.y)} м · вертикальная глубина ${number(end.depth)} м. Траектория рассчитана по измеренному устью и заданному направлению.`;
      }
      function selectHole(holeId) {
        selectedHole = holeId;
        element('observationHoleFilter').value = holeId;
        page = 0; drawSurvey(); drawProfile(); renderTable();
      }
      element('surveyMap').addEventListener('click', event => { const dot = event.target.closest('[data-hole]'); if (dot) selectHole(dot.dataset.hole); });
      element('surveyMap').addEventListener('keydown', event => { if (!['Enter', ' '].includes(event.key)) return; const dot = event.target.closest('[data-hole]'); if (dot) { event.preventDefault(); const id = dot.dataset.hole; selectHole(id); [...element('surveyMap').querySelectorAll('[data-hole]')].find(item => item.dataset.hole === id)?.focus(); } });

      function drawProfile() {
        const hole = holes.find(item => item.hole_id === selectedHole);
        if (!hole) {
          element('holeProfileTitle').textContent = 'В этом источнике нет скважин';
          for (const id of ['holeProfileCaption', 'holeTrajectoryCaption']) element(id).textContent = '';
          for (const id of ['holeProfile', 'holeTrajectory', 'profileKey']) element(id).innerHTML = '';
          return;
        }
        const analyte = element('profileAnalyte').value;
        const logs = tables.borehole_lithology.filter(row => row.hole_id === selectedHole);
        const assays = tables.borehole_assays.filter(row => row.hole_id === selectedHole && row.analyte === analyte);
        const scale = 230 / hole.total_depth_m;
        const axisLeft = 380, axisWidth = 250;
        const maximum = Math.max(...assays.map(row => row.result_value), observations.plan.analytes.find(item => item.analyte === analyte).detection_limit);
        element('holeProfileTitle').textContent = selectedHole;
        element('holeProfileCaption').textContent = `Устье X ${number(hole.x_m)} · Y ${number(hole.y_m)} м · ствол ${number(hole.total_depth_m)} м · угол ${number(hole.dip_deg)}° · азимут ${number(hole.azimuth_deg)}°`;
        let markup = '<text x="12" y="18" font-size="11" fill="#486581">Вдоль ствола</text><text x="162" y="18" font-size="12" fill="#486581">Описание керна</text><text x="380" y="18" font-size="12" fill="#486581">Содержание по пробам</text>';
        for (let index = 0; index <= 5; index++) {
          const y = 36 + index * 46;
          markup += `<path d="M 105 ${y} H 640" stroke="#e8edf2"/><text x="94" y="${y + 4}" text-anchor="end" font-size="11" fill="#627d98">${number(index * hole.total_depth_m / 5)} м</text>`;
        }
        for (const log of logs) {
          const color = rocks[log.observed_rock_id]?.color || '#b7ccd8';
          const y = 36 + log.from_m * scale, h = (log.to_m - log.from_m) * scale;
          markup += `<rect x="118" y="${y}" width="50" height="${h}" fill="${escape(color)}" stroke="white" stroke-width=".7"><title>${escape(log.observed_rock_name)} · ${number(log.from_m)}–${number(log.to_m)} м</title></rect>`;
          if (h > 13) markup += `<text x="180" y="${y + h / 2 + 4}" font-size="10" fill="#486581">${escape(log.observed_rock_name)}</text>`;
        }
        for (const assay of assays) {
          const below = assay.result_qualifier === 'lt';
          const y = 36 + assay.from_m * scale, h = Math.max(.6, (assay.to_m - assay.from_m) * scale - .4);
          markup += `<rect x="${axisLeft}" y="${y}" width="${Math.max(1, assay.result_value / maximum * axisWidth)}" height="${h}" fill="${below ? '#b7c9d5' : '#168c86'}"><title>${number(assay.from_m)}–${number(assay.to_m)} м: ${below ? '&lt; ' : ''}${number(assay.result_value)} ${escape(assay.unit)}</title></rect>`;
        }
        markup += `<text x="${axisLeft}" y="286" font-size="10" fill="#627d98">0</text><text x="${axisLeft + axisWidth}" y="286" text-anchor="end" font-size="10" fill="#627d98">${number(maximum)} ${escape(observations.plan.analytes.find(item => item.analyte === analyte).unit)}</text>`;
        element('holeProfile').innerHTML = markup;
        element('profileKey').innerHTML = '<span><i style="background:#168c86"></i>Измеренный результат</span><span><i style="background:#b7c9d5"></i>Верхняя граница: ниже предела обнаружения</span><span>Пустой участок — проба пропущена</span>';
        drawTrajectory(hole);
      }
      element('profileAnalyte').addEventListener('change', drawProfile);

      const tabButtons = {};
      function buildTableTabs(keys) {
        element('observationTabs').innerHTML = '';
        for (const key of Object.keys(tabButtons)) delete tabButtons[key];
        activeTable = keys[0];
        for (const key of keys) {
          const button = document.createElement('button'); button.className = 'data-tab'; button.textContent = tableNames[key];
          button.addEventListener('click', () => { activeTable = key; page = 0; renderTable(); });
          tabButtons[key] = button; element('observationTabs').appendChild(button);
        }
      }
      function renderTable() {
        for (const [key, button] of Object.entries(tabButtons)) button.setAttribute('aria-pressed', String(key === activeTable));
        const holeFilter = element('observationHoleFilter').value;
        const analyteFilter = element('observationAnalyteFilter').value;
        const fields = observations.table_fields[activeTable] || [];
        const trenchFilter = element('observationTrenchFilter').value;
        const sampleFilter = element('observationSampleFilter').value.trim();
        const qcFilter = element('observationQcFilter').value;
        const rows = sourceRows(activeTable).filter(row =>
          (!fields.includes('hole_id') || !holeFilter || row.hole_id === holeFilter) &&
          (!fields.includes('trench_id') || !trenchFilter || row.trench_id === trenchFilter) &&
          (!fields.includes('analyte') || !analyteFilter || row.analyte === analyteFilter) &&
          (!fields.includes('sample_id') || !sampleFilter || row.sample_id.includes(sampleFilter)) &&
          (activeTable !== 'quality_control' || !qcFilter || row.qc_flag === qcFilter));
        page = Math.max(0, Math.min(page, Math.ceil(rows.length / pageSize) - 1));
        element('holeFilterLabel').classList.toggle('hidden', !fields.includes('hole_id'));
        element('sourceFilterLabel').classList.toggle('hidden', !fields.includes('hole_id') || !drillingSources.length);
        const sourceSelected = sourceByKind.has(element('observationSourceFilter').value);
        element('downloadDrillingSource').classList.toggle('hidden', !sourceSelected || !fields.includes('hole_id'));
        element('downloadObservationCsv').textContent = sourceSelected ? 'CSV источника' : 'CSV всей таблицы';
        element('trenchFilterLabel').classList.toggle('hidden', !fields.includes('trench_id'));
        element('analyteFilterLabel').classList.toggle('hidden', !fields.includes('analyte'));
        element('sampleFilterLabel').classList.toggle('hidden', !fields.includes('sample_id'));
        element('qcFilterLabel').classList.toggle('hidden', activeTable !== 'quality_control');
        element('observationTableHead').innerHTML = '<tr>' + fields.map(field => `<th scope="col" title="${escape(field)}">${escape(fieldNames[field] || field)}</th>`).join('') + '</tr>';
        element('observationTableBody').innerHTML = rows.slice(page * pageSize, (page + 1) * pageSize).map(row => '<tr>' + fields.map(field => {
          const value = row[field];
          const display = value === null || value === undefined || value === '' ? '—' : typeof value === 'number' ? number(value) : categoryNames[value] || value;
          return `<td>${escape(display)}</td>`;
        }).join('') + '</tr>').join('') || `<tr><td colspan="${fields.length}">Нет наблюдений для выбранных фильтров</td></tr>`;
        element('observationCount').textContent = `${number(rows.length)} записей`;
        element('observationPageInfo').textContent = rows.length ? `${page * pageSize + 1}–${Math.min(rows.length, (page + 1) * pageSize)} из ${number(rows.length)} · пустые значения обозначены «—»` : 'Нет записей';
        element('observationPrevious').disabled = page === 0;
        element('observationNext').disabled = (page + 1) * pageSize >= rows.length;
      }
      element('observationHoleFilter').addEventListener('change', () => {
        page = 0;
        if (element('observationHoleFilter').value) { selectedHole = element('observationHoleFilter').value; drawSurvey(); drawProfile(); }
        renderTable();
      });
      element('observationAnalyteFilter').addEventListener('change', () => { page = 0; renderTable(); });
      element('observationPrevious').addEventListener('click', () => { page--; renderTable(); });
      element('observationNext').addEventListener('click', () => { page++; renderTable(); });
      drawSurvey(); drawProfile();
      __METHODS_SCRIPT__
      renderRecognition(RECOGNITION_DATA);
    })(OBSERVATION_DATA);
'''

WORKSPACE_STYLES += METHODS_STYLES
EXPEDITION_PANEL = EXPEDITION_PANEL.replace('__METHOD_OVERVIEWS__', METHODS_HTML)
WORKSPACE_SCRIPT = WORKSPACE_SCRIPT.replace('__METHODS_SCRIPT__', METHODS_SCRIPT)
