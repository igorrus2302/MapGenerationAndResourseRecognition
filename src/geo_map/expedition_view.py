"""Offline workspace tabs and views that render only public expedition records."""

from .expedition_methods_view import FIELD_METHODS_HTML, METHODS_SCRIPT, METHODS_STYLES, PRELIMINARY_METHODS_HTML
from .preliminary_view import PRELIMINARY_SCRIPT
from .observation_import_view import IMPORT_ENGINE, IMPORT_STYLES, IMPORT_UI, import_panel
from .reconstruction_view import RECONSTRUCTION_STYLES, RECONSTRUCTION_HTML, MINERALS_PANEL, RECONSTRUCTION_SCRIPT

WORKSPACE_STYLES = r'''
    .workspace-tabs {
      flex: 0 0 auto; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
      background: var(--ink); padding: 0 26px; gap: 0;
    }
    .workspace-tab {
      display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 4px;
      width: 100%; min-height: 62px; padding: 10px 14px; border: 0; border-radius: 0;
      border-top: 3px solid transparent; border-right: 1px solid #ffffff24;
      color: #e8e8dd; background: transparent; text-align: left; line-height: 1.3; font-size: 13px; overflow-wrap: anywhere;
    }
    .workspace-tab:first-child { border-left: 1px solid #ffffff24; }
    .workspace-tab:hover:not(:disabled) { color: #fff; background: #3a4d40; }
    .workspace-tab[aria-selected="true"] { color: var(--ink); background: var(--paper); border-top-color: var(--highlight); }
    .workspace-tab[aria-selected="true"]:hover { color: var(--ink); background: var(--paper); }
    .workspace-tab:focus-visible { outline-offset: -4px; }
    .tab-number { font: 11px/1 var(--mono); color: #c3c9b8; letter-spacing: .04em; }
    .workspace-tab[aria-selected="true"] .tab-number { color: var(--highlight); }
    .workspace-page { flex: 1 1 0; min-height: 0; min-width: 0; overflow: auto; padding: 26px; }
    #preliminaryPanel { display: flex; flex-direction: column; }
    #preliminaryEmpty, #preliminaryContent { flex: none; }
    #preliminaryEmpty { margin: auto; }
    #expeditionPanel { display: flex; flex-direction: column; }
    #expeditionEmpty, #expeditionContent { flex: none; }
    #expeditionEmpty { margin: auto; }
    .expedition-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px 20px; padding-bottom: 16px; border-bottom: 1px solid var(--line); margin-bottom: 20px; }
    .expedition-heading > div { flex: 1 1 280px; min-width: 0; }
    .expedition-heading h2 { margin: 0 0 6px; font: 500 28px/1.2 var(--heading); color: var(--ink); }
    .expedition-heading p { margin: 0; color: var(--muted); font-size: 13px; }
    .primary-button { width: auto; padding: 10px 16px; color: white; background: var(--accent); border-color: var(--accent); white-space: normal; }
    .primary-button:hover:not(:disabled) { color: white; background: var(--accent-hover); border-color: var(--accent-hover); }
    .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--line); background: var(--line); margin-bottom: 22px; }
    .metric-card { min-width: 0; background: var(--surface); padding: 14px 18px; }
    .metric-card strong { display: block; margin-bottom: 4px; font-size: clamp(20px, 2vw, 28px); line-height: 1.2; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .metric-card span { display: block; color: var(--muted); font-size: 12px; }
    .expedition-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: stretch; margin-bottom: 18px; }
    .panel-card { background: var(--surface); border: 1px solid var(--line); padding: 18px; min-width: 0; }
    .panel-card h3 { margin: 0 0 6px; font-size: 16px; font-weight: 650; color: var(--ink); }
    .muted { color: var(--muted); font-size: 12px; }
    .survey-map { width: 100%; height: auto; max-height: 460px; display: block; }
    .survey-map, .hole-profile, .downhole-log-profile, .hole-trajectory, .method-map, .method-profile { font-variant-numeric: tabular-nums; }
    .hole-dot { cursor: pointer; }
    .hole-dot:focus, .hole-dot:hover { outline: none; stroke: var(--highlight); stroke-width: 3; }
    .profile-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px 14px; flex-wrap: wrap; }
    .profile-heading > div { min-width: 0; }
    .profile-heading select { width: auto; max-width: min(100%, 260px); }
    .selection-controls { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: flex-end; margin: 12px 0; }
    .selection-controls label { flex: 1 1 160px; min-width: 0; margin: 0; }
    .selection-controls select { display: block; width: 100%; margin-top: 5px; }
    .selection-detail { color: var(--muted); font-size: 12px; line-height: 1.7; margin: 10px 0 0; overflow-wrap: anywhere; }
    .selection-detail strong { color: var(--ink); }
    .hole-profile { width: 100%; height: auto; max-height: 460px; display: block; }
    .downhole-log-profile { width: 100%; height: auto; max-height: 460px; display: block; }
    .downhole-log-panel { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--line); }
    .hole-trajectory { width: 100%; height: auto; max-height: 320px; display: block; margin-top: 16px; }
    .profile-key { display: flex; gap: 8px 12px; flex-wrap: wrap; font-size: 11px; color: var(--muted); margin-top: 8px; }
    .profile-key span { display: inline-flex; align-items: center; gap: 5px; }
    .profile-key i { width: 10px; height: 10px; border-radius: 1px; display: inline-block; flex: 0 0 auto; }
    .data-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .data-heading > div { min-width: 0; }
    .data-heading button { width: auto; }
    .data-tabs { display: flex; gap: 5px; flex-wrap: wrap; margin: 12px 0; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
    .data-tab { width: auto; min-height: 34px; font-size: 12px; background: transparent; }
    .data-tab[aria-pressed="true"] { color: var(--ink); background: var(--accent-tint); border-color: var(--accent); }
    .data-filters { display: flex; gap: 10px 14px; align-items: end; flex-wrap: wrap; margin-bottom: 12px; }
    .data-filters label { flex: 1 1 155px; margin: 0; min-width: 0; max-width: 280px; }
    .data-filters select { display: block; margin-top: 5px; font-size: 12px; }
    .table-scroll { overflow: auto; max-height: 380px; border: 1px solid var(--line); }
    .observation-table { border-collapse: collapse; width: 100%; font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .observation-table th { background: var(--surface-muted); color: var(--ink); font-weight: 650; position: sticky; top: 0; z-index: 1; }
    .observation-table th, .observation-table td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--line); }
    .observation-table tbody tr:nth-child(even) { background: #f6f4ed; }
    .observation-table tbody tr:hover { background: var(--accent-tint); }
    .table-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; font-size: 12px; color: var(--muted); }
    .page-buttons { display: flex; gap: 6px; }
    .page-buttons button { width: auto; min-height: 32px; font-size: 12px; }
    button:disabled { opacity: .46; cursor: default; }
    .empty-card { width: min(590px, 100%); padding: 28px 30px; background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--highlight); }
    .empty-card h2 { font: 500 28px/1.2 var(--heading); color: var(--ink); margin: 0 0 12px; }
    .empty-card p { color: var(--muted); line-height: 1.7; margin: 0 0 14px; }
    .empty-card-actions { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; margin-top: 18px; }
    .empty-card-actions button { width: 100%; min-height: 44px; padding: 10px 16px; white-space: normal; overflow-wrap: anywhere; text-align: center; }
    @media (max-width: 1050px) {
      .workspace-tabs { padding-inline: 14px; }
      .workspace-tab { padding-inline: 10px; }
    }
    @media (max-width: 860px) {
      .workspace-tabs { padding: 0; grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .workspace-tab { font-size: 12px; min-height: 59px; }
      .workspace-page { flex: none; min-height: 60vh; padding: 16px; overflow: visible; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .expedition-heading { align-items: flex-start; }
      .expedition-heading h2 { font-size: 24px; }
      .panel-card { padding: 14px; }
    }
    @media (max-width: 520px) {
      .workspace-tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .empty-card { padding: 22px 18px; }
      .empty-card h2 { font-size: 24px; }
      .data-filters label { max-width: 100%; }
    }
'''

WORKSPACE_TABS = r'''
  <nav class="workspace-tabs" role="tablist" aria-label="Этапы исследования">
    <button class="workspace-tab" id="tab-truth" role="tab" aria-controls="truthPanel" aria-selected="true" data-workspace="truth"><span class="tab-number">01</span>Истинная карта</button>
    <button class="workspace-tab" id="tab-preliminary" role="tab" aria-controls="preliminaryPanel" aria-selected="false" tabindex="-1" data-workspace="preliminary"><span class="tab-number">02</span>Предварительные наблюдения</button>
    <button class="workspace-tab" id="tab-expedition" role="tab" aria-controls="expeditionPanel" aria-selected="false" tabindex="-1" data-workspace="expedition"><span class="tab-number">03</span>Разведочная экспедиция</button>
    <button class="workspace-tab" id="tab-recognized" role="tab" aria-controls="recognizedPanel" aria-selected="false" tabindex="-1" data-workspace="recognized"><span class="tab-number">04</span>Распознанная карта</button>
    <button class="workspace-tab" id="tab-minerals" role="tab" aria-controls="mineralsPanel" aria-selected="false" tabindex="-1" data-workspace="minerals"><span class="tab-number">05</span>Найденные ископаемые</button>
  </nav>
'''

WORKSPACE_PANELS = r'''
  <section id="preliminaryPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-preliminary">
    <div id="preliminaryEmpty" class="empty-card">
      <h2>Предварительные наблюдения</h2>
      <p id="preliminaryStatus" aria-live="polite">Соберите данные о магнитном поле, гамма-фоне, рельефе и обнажениях на текущей карте.</p>
      <div class="empty-card-actions">
        <button id="collectPreliminary" type="button" class="primary-button">Собрать наблюдения</button>
        <button id="openManualPreliminary" type="button">Открыть разделы для ручной загрузки</button>
      </div>
    </div>
    <div id="preliminaryContent" class="hidden">
      <div class="expedition-heading">
        <div><h2>Предварительные наблюдения</h2><p>Данные съёмки участка до бурения и отбора проб.</p></div>
      </div>
      <div class="method-sections" id="preliminarySections" aria-label="Виды предварительных наблюдений"></div>
      __PRELIMINARY_METHODS__
      <div class="panel-card">
        <div class="data-heading">
          <div><h3 id="preliminaryDataTitle"></h3><span id="preliminaryCount" class="muted" aria-live="polite"></span></div>
          <div class="data-downloads"><button id="downloadPreliminaryGeoJson">Скачать GeoJSON</button><button id="downloadPreliminaryCsv">CSV всей таблицы</button></div>
        </div>
        __PRELIMINARY_IMPORT__
        <div class="table-scroll"><table class="observation-table"><thead id="preliminaryTableHead"></thead><tbody id="preliminaryTableBody"></tbody></table></div>
        <div class="table-footer"><span id="preliminaryPageInfo" aria-live="polite"></span><div class="page-buttons"><button id="preliminaryPrevious">← Назад</button><button id="preliminaryNext">Далее →</button></div></div>
      </div>
    </div>
  </section>
  <section id="expeditionPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-expedition">
    <div id="expeditionEmpty" class="empty-card hidden">
      <h2>Разведочная экспедиция</h2>
      <p id="expeditionStatus" aria-live="polite">Сначала соберите предварительные наблюдения на вкладке 02.</p>
      <div class="empty-card-actions"><button id="startExpedition" type="button" class="primary-button" disabled>Запустить экспедицию</button></div>
    </div>
    <div id="expeditionContent">
      <div class="expedition-heading">
        <div><h2 id="expeditionTitle"></h2><p id="expeditionSubtitle"></p></div>
        <button id="downloadObservations" class="primary-button">Скачать оба этапа · JSON</button>
      </div>
      <div class="metric-grid" id="expeditionMetrics"></div>
      <div class="method-sections" id="expeditionSections" aria-label="Виды разведочных наблюдений"></div>
      <div class="expedition-grid" id="boreholeOverview">
        <div class="panel-card">
          <h3>План бурения</h3><div class="muted">Нажмите на скважину, чтобы открыть её данные</div>
          <div class="selection-controls"><label id="profileSourceLabel" class="hidden">Источник бурения<select id="profileSource"></select></label></div>
          <svg id="surveyMap" class="survey-map" viewBox="0 0 520 300" role="group" aria-label="Положения наблюдённых скважин"></svg>
          <div class="muted" id="surveyCaption"></div>
          <div class="profile-key hidden" id="surveyPlacementKey" aria-label="Основания выбора скважин"></div>
        </div>
        <div class="panel-card">
          <div class="profile-heading"><div><h3 id="holeProfileTitle"></h3><div id="holeProfileCaption" class="muted" aria-live="polite"></div></div></div>
          <div class="selection-controls">
            <label>Скважина<select id="profileHole"></select></label>
            <label>Компонент<select id="profileAnalyte"></select></label>
          </div>
          <svg id="holeProfile" class="hole-profile" viewBox="0 0 700 300" role="img" aria-label="Литологический журнал и анализы выбранной скважины"></svg>
          <div class="profile-key" id="profileKey"></div>
          <div id="gammaProfilePanel" class="downhole-log-panel hidden">
            <h3>Гамма-каротаж</h3>
            <div class="muted" id="gammaProfileCaption"></div>
            <svg id="gammaProfile" class="downhole-log-profile" viewBox="0 0 700 300" role="img" aria-label="Гамма-сигнал вдоль ствола"></svg>
          </div>
          <div id="magneticProfilePanel" class="downhole-log-panel hidden">
            <h3>Магнитный каротаж</h3>
            <div class="muted" id="magneticProfileCaption"></div>
            <svg id="magneticProfile" class="downhole-log-profile" viewBox="0 0 700 300" role="img" aria-label="Магнитная восприимчивость вдоль ствола"></svg>
          </div>
          <svg id="holeTrajectory" class="hole-trajectory" viewBox="0 0 700 200" role="img" aria-label="Траектория выбранной скважины в вертикальной плоскости"></svg>
          <div class="muted" id="holeTrajectoryCaption"></div>
        </div>
      </div>
      __FIELD_METHODS__
      <div class="panel-card">
        <div class="data-heading"><div><h3 id="dataSectionTitle">Данные экспедиции</h3><div class="muted">Наблюдения и измерения выбранного раздела</div></div><div class="data-downloads"><button id="downloadMethodGeoJson" class="hidden">Скачать GeoJSON</button><button id="downloadDrillingSource" class="hidden">Скачать источник · JSON</button><button id="downloadObservationCsv">CSV всей таблицы</button></div></div>
        <div class="data-tabs" id="observationTabs"></div>
        __FIELD_IMPORT__
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
    </div>
  </section>
  <section id="recognizedPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-recognized">
    <div class="empty-card" id="recognitionEmpty"><h2>Поиск по наблюдениям</h2><p>Результаты поиска ещё не загружены.</p></div>
    <div id="recognitionContent" class="hidden">
      __RECONSTRUCTION_HTML__
    </div>
  </section>
  __MINERALS_PANEL__
'''

WORKSPACE_SCRIPT = r'''
    (() => {
      const tabs = [...document.querySelectorAll('.workspace-tab')];
      const panels = {truth: 'truthPanel', preliminary: 'preliminaryPanel', expedition: 'expeditionPanel', recognized: 'recognizedPanel', minerals: 'mineralsPanel'};
      function activate(name) {
        if (!Object.hasOwn(panels, name)) name = 'truth';
        for (const [key, id] of Object.entries(panels)) document.getElementById(id).classList.toggle('hidden', key !== name);
        for (const tab of tabs) {
          const selected = tab.dataset.workspace === name;
          tab.setAttribute('aria-selected', String(selected));
          tab.tabIndex = selected ? 0 : -1;
        }
        if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
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

    // Fieldwork and recognition render public records. The preliminary survey samples the map on demand.
    ((observations) => {
      const element = id => document.getElementById(id);
      const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
      const number = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 8});
      const tableNames = {borehole_collars: 'Скважины', borehole_lithology: 'Литология', borehole_assays: 'Анализы проб', downhole_properties: 'Физические свойства', downhole_gamma: 'Гамма-каротаж', downhole_magnetic: 'Магнитный каротаж', structural_observations: 'Контакты и разломы', fault_intersections: 'Интервалы нарушений', surface_geochemistry: 'Почвенные пробы', trenches: 'Положение траншей', trench_intervals: 'Описание дна', trench_samples: 'Канавные пробы', quality_control: 'Контрольные пробы'};
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
        strike_deg: 'Простирание, °', dip_direction_deg: 'Направление падения, °', offset_estimate_m: 'Оценка смещения, м', observation_method: 'Метод наблюдения', notes: 'Примечания', counting_time_s: 'Время счёта, с', magnetic_susceptibility_si: 'Магнитная восприимчивость, СИ', magnetic_sigma_si: 'Погрешность восприимчивости, СИ'
      };
      const categoryNames = {completed: 'Завершена', medium: 'Средняя', high: 'Высокая', low: 'Низкая', contact: 'Контакт', primary: 'Первичная', not_checked: 'Не проверено', core_logging: 'Описание керна', synthetic_core: 'Синтетическое бурение', synthetic_core_measurement: 'Синтетическое измерение', synthetic_assay: 'Синтетический анализ', local_cartesian: 'Локальная, м', lt: 'Ниже предела'};
      categoryNames.synthetic_gamma_logging = 'Синтетический гамма-каротаж';
      categoryNames.synthetic_magnetic_logging = 'Синтетический магнитный каротаж';
      const pageSize = 50;
      const terrainTypes = {
        hill: {label: 'Возвышенность', color: '#ad542c'}, depression: {label: 'Понижение', color: '#226caa'},
        slope: {label: 'Склон', color: '#6544a6'}, flat: {label: 'Ровный участок', color: '#288362'},
        undetermined: {label: 'Мало данных', color: '#64748b'}
      };
      __IMPORT_ENGINE__
      __IMPORT_UI__
      __PRELIMINARY_SCRIPT__
      const preliminaryTables = ['magnetic_observations','gamma_observations','terrain_observations','outcrop_observations'];
      function updateExpeditionStart() {
        if (EXPEDITION_COLLECTED) return;
        const start = element('startExpedition');
        const ready = PRELIMINARY_COLLECTED || preliminaryTables.some(name=>observations?.tables[name]?.length);
        start.disabled = !EXPEDITION_ENDPOINT || !ready;
        element('expeditionStatus').textContent = !EXPEDITION_ENDPOINT
          ? 'Для запуска новой экспедиции используйте интерактивный просмотрщик (main.py).'
          : ready ? 'Предварительные наблюдения готовы. Запустите бурение, опробование, полевые измерения и поиск месторождений.'
          : 'Сначала соберите предварительные наблюдения или загрузите их вручную на вкладке 02.';
      }
      if (!EXPEDITION_COLLECTED) {
        document.getElementById('expeditionEmpty').classList.remove('hidden');
        document.getElementById('expeditionContent').classList.add('hidden');
        updateExpeditionStart();
        const start = element('startExpedition');
        start.addEventListener('click', async () => {
          if (start.disabled) return;
          start.disabled = true;
          element('expeditionStatus').textContent = 'Выполняется разведочная экспедиция и распознавание месторождений…';
          try {
            const tables = Object.fromEntries(preliminaryTables.map(name=>[name, observations.tables[name] || []]));
            const response = await fetch(EXPEDITION_ENDPOINT, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(tables)});
            if (!response.ok) {
              const error = await response.json();
              throw new Error(error.error || 'Ошибка запуска экспедиции');
            }
            location.reload();
          } catch (error) {
            start.disabled = false;
            element('expeditionStatus').textContent = 'Не удалось запустить экспедицию. ' + error.message;
          }
        });
        return;
      }
      const tables = observations.tables;
      const holes = tables.borehole_collars;
      const hybridDrilling = observations.plan.layout === 'hybrid';
      const drillingTargets = new Map(Object.entries(observations.drilling_targets ?? {}));
      const drillingKinds = {
        random: {label: 'Случайное размещение', color: '#355d48'},
        magnetic: {label: 'Магнитная аномалия', color: '#b45d15'},
        gamma: {label: 'Повышенный гамма-фон', color: '#783fb3'}
      };
      if (hybridDrilling) {
        const counts = {random: holes.length - drillingTargets.size, magnetic: 0, gamma: 0};
        for (const target of drillingTargets.values()) counts[target.method]++;
        const key = element('surveyPlacementKey');
        key.classList.remove('hidden');
        key.innerHTML = Object.entries(drillingKinds).filter(([kind]) => counts[kind]).map(([kind, {label, color}]) =>
          `<span><i style="background:${color}"></i>${label} · ${counts[kind]}</span>`).join('');
      }
      const drillingSources = observations.borehole_sources || (observations.borehole_sources = []);
      const sourceByKind = new Map(drillingSources.map(source => [source.kind, source]));
      const rocks = Object.fromEntries(observations.rock_catalog.map(rock => [rock.id, rock]));
      let selectedHole = holes[0]?.hole_id;
      let activeTable = 'borehole_collars';
      let page = 0;
      const summary = observations.summary;
      element('expeditionTitle').textContent = observations.campaign.title;
      element('expeditionSubtitle').textContent = `${observations.campaign.campaign_id} · ${observations.campaign.date} · бурение, полевые пробы и лабораторные анализы`;
      function drawExpeditionMetrics() {
      element('expeditionMetrics').innerHTML = [[summary.hole_count, 'скважин'], [`${number(summary.drilled_m)} м`, 'пройдено бурением'], [number(summary.total_sample_count ?? summary.sample_count), 'полевых проб всех методов'], [number(summary.total_assay_count ?? summary.assay_count), 'результатов полевых проб']].map(([value, label]) => `<div class="metric-card"><strong>${escape(value)}</strong><span>${label}</span></div>`).join('');
      }
      drawExpeditionMetrics();
      const options = holes.map(hole => `<option value="${escape(hole.hole_id)}">${escape(hole.hole_id)}</option>`).join('');
      element('observationHoleFilter').innerHTML = '<option value="">Все скважины</option>' + options;
      function refreshSourceOptions() {
        const sourceFilter=element('observationSourceFilter'), previous=sourceFilter.value;
        sourceByKind.clear();for(const source of drillingSources)sourceByKind.set(source.kind,source);
        sourceFilter.innerHTML = '<option value="">Все источники бурения</option>' + drillingSources.map(source => `<option value="${escape(source.kind)}">${escape(source.title)} · ${source.summary.hole_count} скв.</option>`).join('');
        sourceFilter.value=sourceByKind.has(previous)?previous:'';
        element('profileSource').innerHTML = sourceFilter.innerHTML;
        element('profileSource').value=sourceFilter.value;
      }
      refreshSourceOptions();
      element('profileSourceLabel').classList.toggle('hidden', !drillingSources.length);
      element('profileHole').innerHTML = options;
      const analyteOptions = observations.plan.analytes.map(item => `<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');
      element('profileAnalyte').innerHTML = analyteOptions;
      const filterAnalytes = [...new Map([...observations.plan.analytes, ...(observations.plan.methods?.surface_geochemistry?.analytes || [])].map(item => [item.analyte, item])).values()];
      element('observationAnalyteFilter').innerHTML = '<option value="">Все компоненты</option>' + filterAnalytes.map(item => `<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');

      function addMethodButtons(methods, containerId, activate) {
        const container = element(containerId);
        return Object.fromEntries(Object.entries(methods).map(([key, method]) => {
          const button = document.createElement('button');
          button.className = 'method-section';
          button.textContent = method.label;
          button.dataset.method = key;
          button.addEventListener('click', () => activate(key));
          container.appendChild(button);
          return [key, button];
        }));
      }
      function mapFrame(dimensions = observations.campaign) {
        const width = dimensions.width_m, height = dimensions.height_m;
        const scale = Math.min(560 / width, 230 / height), w = width * scale, h = height * scale;
        const left = (650 - w) / 2, top = 22;
        const point = (x, y) => ({x: left + x * scale, y: top + h - y * scale});
        const markup = `<rect x="${left}" y="${top}" width="${w}" height="${h}" rx="0" fill="#f4f0e5" stroke="#b8b8a9"/><text x="${left}" y="${top - 7}" font-size="11" fill="#62675e">Y · ${number(height)} м</text><text x="${left}" y="${top + h + 20}" font-size="11" fill="#62675e">0</text><text x="${left + w}" y="${top + h + 20}" text-anchor="end" font-size="11" fill="#62675e">X · ${number(width)} м</text>`;
        return {point, markup};
      }
      function download(content, filename, type) {
        const url = URL.createObjectURL(new Blob([content], {type}));
        const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      function downloadCsv(fields, rows, filename) {
        const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
        const lines = [fields, ...rows.map(row => fields.map(field => row[field]))];
        download(lines.map(row => row.map(quote).join(',')).join('\r\n') + '\r\n', filename, 'text/csv;charset=utf-8');
      }
      function downloadGeoJson(name) {
        if (name && observations.geojson?.[name]) download(JSON.stringify(observations.geojson[name], null, 2), `${name}.geojson`, 'application/geo+json');
      }
      element('downloadObservations').addEventListener('click', () => download(JSON.stringify(observations, null, 2), 'observations.json', 'application/json'));
      element('downloadObservationCsv').addEventListener('click', () => {
        const fields = observations.table_fields[activeTable];
        const source = sourceByKind.get(element('observationSourceFilter').value);
        downloadCsv(fields, sourceRows(activeTable), `${source ? source.kind + '_' : ''}${activeTable}.csv`);
      });
      function sourceRows(name) {
        const source = sourceByKind.get(element('observationSourceFilter').value);
        if (!source || !observations.table_fields[name]?.includes('hole_id')) return tables[name] || [];
        const ids = new Set(source.hole_ids);
        return (tables[name] || []).filter(row => ids.has(row.hole_id));
      }
      function updateSourceHoles() {
        const available = sourceRows('borehole_collars');
        const availableOptions = available.map(hole => `<option value="${escape(hole.hole_id)}">${escape(hole.hole_id)} · ${hole.dip_deg === -90 ? 'вертикальная' : 'наклонная'}</option>`).join('');
        element('observationHoleFilter').innerHTML = '<option value="">Все скважины источника</option>' + availableOptions;
        element('profileSource').value = element('observationSourceFilter').value;
        element('profileHole').innerHTML = availableOptions || '<option value="">Нет скважин</option>';
        element('profileHole').disabled = !available.length;
        if (!available.some(hole => hole.hole_id === selectedHole)) selectedHole = available[0]?.hole_id;
        drawSurvey(); drawProfile();
      }
      element('observationSourceFilter').addEventListener('change', () => {
        page = 0; updateSourceHoles(); renderTable();
      });
      element('profileSource').addEventListener('change', () => {
        element('observationSourceFilter').value = element('profileSource').value;
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
        let markup = `<rect x="${left}" y="${top}" width="${w}" height="${h}" rx="0" fill="#f4f0e5" stroke="#b8b8a9"/>`;
        for (let index = 1; index < 5; index++) {
          markup += `<path d="M ${left + w * index / 5} ${top} v ${h} M ${left} ${top + h * index / 5} h ${w}" stroke="#dcd9ce" stroke-dasharray="3 4"/>`;
        }
        markup += `<text x="${left}" y="${top + h + 19}" font-size="11" fill="#62675e">0</text><text x="${left + w}" y="${top + h + 19}" text-anchor="end" font-size="11" fill="#62675e">X · ${number(width)} м</text><text x="${left}" y="${top - 6}" font-size="10" fill="#62675e">Y · ${number(height)} м</text>`;
        for (const hole of sourceRows('borehole_collars')) {
          const cx = left + hole.x_m * scale, cy = top + h - hole.y_m * scale;
          const end = holePosition(hole, hole.total_depth_m);
          const ex = left + end.x * scale, ey = top + h - end.y * scale;
          const selected = hole.hole_id === selectedHole;
          const target = drillingTargets.get(hole.hole_id);
          const kind = target?.method ?? 'random';
          const placement = hybridDrilling ? ` · ${drillingKinds[kind].label}${target ? ` · ${target.observation_id}` : ''}` : '';
          const color = hybridDrilling ? drillingKinds[kind].color : selected ? '#a35a35' : '#355d48';
          const border = selected && hybridDrilling ? '#25362e' : 'white';
          if (hole.dip_deg !== -90) markup += `<line class="hole-dot" data-hole="${escape(hole.hole_id)}" data-hole-trajectory="${escape(hole.hole_id)}" x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="${color}" stroke-width="${selected ? 4 : 2}" opacity="${selected ? 1 : .55}"><title>${escape(hole.hole_id)} · проекция ствола</title></line><circle cx="${ex}" cy="${ey}" r="3" fill="${color}"/>`;
          markup += `<circle class="hole-dot" role="button" tabindex="0" aria-label="${escape(hole.hole_id + placement)}" aria-pressed="${selected}" data-hole="${escape(hole.hole_id)}" cx="${cx}" cy="${cy}" r="${selected ? 7 : 5}" fill="${color}" stroke="${border}" stroke-width="2"><title>${escape(hole.hole_id + placement)} · ствол ${number(hole.total_depth_m)} м · угол ${number(hole.dip_deg)}° · азимут ${number(hole.azimuth_deg)}°</title></circle>`;
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
      __RECONSTRUCTION_SCRIPT__
      function renderRecognition(result) {
        if (!result) return;
        renderReconstruction(result);
        element('recognitionEmpty').classList.add('hidden');
        element('recognitionContent').classList.remove('hidden');
        element('downloadRecognition').addEventListener('click', () => download(JSON.stringify(result, null, 2), 'recognition.json', 'application/json'));
      }
      function drawTrajectory(hole) {
        const end = holePosition(hole, hole.total_depth_m);
        const scale = Math.min(480 / Math.max(1, end.horizontal), 135 / Math.max(1, end.depth));
        const x = 110 + end.horizontal * scale, y = 24 + end.depth * scale;
        element('holeTrajectory').innerHTML = `<text x="18" y="14" font-size="12" fill="#555e50">Вертикальная глубина</text><path d="M 110 24 V 164 H 630" fill="none" stroke="#b8b8a9"/><path d="M 110 24 V ${y} H ${x}" fill="none" stroke="#b8b8a9" stroke-dasharray="4 4"/><path data-borehole-path="${escape(hole.hole_id)}" d="M 110 24 L ${x} ${y}" fill="none" stroke="#a35a35" stroke-width="4"/><circle cx="110" cy="24" r="4" fill="#355d48"/><circle cx="${x}" cy="${y}" r="4" fill="#a35a35"/><text x="98" y="${y + 4}" text-anchor="end" font-size="11" fill="#555e50">${number(end.depth)} м</text><text x="${x}" y="181" text-anchor="middle" font-size="11" fill="#555e50">${number(end.horizontal)} м</text><text x="630" y="197" text-anchor="end" font-size="11" fill="#62675e">Горизонтальное отклонение от устья</text>`;
        element('holeTrajectoryCaption').textContent = `Забой: X ${number(end.x)} · Y ${number(end.y)} м · вертикальная глубина ${number(end.depth)} м. Траектория рассчитана по измеренному устью и заданному направлению.`;
      }
      function selectHole(holeId) {
        if (!sourceRows('borehole_collars').some(hole => hole.hole_id === holeId)) return;
        selectedHole = holeId;
        element('observationHoleFilter').value = holeId;
        page = 0; drawSurvey(); drawProfile(); renderTable();
      }
      element('profileHole').addEventListener('change', () => selectHole(element('profileHole').value));
      element('surveyMap').addEventListener('click', event => { const dot = event.target.closest('[data-hole]'); if (dot) selectHole(dot.dataset.hole); });
      element('surveyMap').addEventListener('keydown', event => { if (!['Enter', ' '].includes(event.key)) return; const dot = event.target.closest('[data-hole]'); if (dot) { event.preventDefault(); const id = dot.dataset.hole; selectHole(id); [...element('surveyMap').querySelectorAll('[data-hole]')].find(item => item.dataset.hole === id)?.focus(); } });

      const boreholeLogChannels = {
        gamma: {table:'downhole_gamma', field:'gamma_count_rate_cps', sigma:'gamma_sigma_cps', unit:'имп/с', title:'Гамма-сигнал, имп/с', color:'#9354b5', axisFactor:1, minimumSpan:1, signed:false},
        magnetic: {table:'downhole_magnetic', field:'magnetic_susceptibility_si', sigma:'magnetic_sigma_si', unit:'СИ', title:'Магнитная восприимчивость, ×10⁻³ СИ', color:'#a35a35', axisFactor:1000, minimumSpan:0.000001, signed:true},
      };
      function drawBoreholeLogProfile(hole, channel) {
        const spec=boreholeLogChannels[channel], prefix=channel+'Profile';
        const rows=(tables[spec.table]||[]).filter(row=>row.hole_id===hole?.hole_id).sort((a,b)=>a.from_m-b.from_m);
        element(prefix+'Panel').classList.toggle('hidden',!rows.length);
        if(!rows.length){element(prefix).innerHTML='';element(prefix+'Caption').textContent='';return;}
        const peak=rows.reduce((value,row)=>Math.max(value,row[spec.field]),-Infinity);
        const minimum=spec.signed?rows.reduce((value,row)=>Math.min(value,row[spec.field]),0):0;
        const maximum=Math.max(minimum+spec.minimumSpan,0,peak);
        const left=105,width=540,top=36,height=230;
        const x=value=>left+(value-minimum)/(maximum-minimum)*width;
        const y=depth=>top+depth/hole.total_depth_m*height;
        const measured=value=>Number(value).toLocaleString('ru-RU',{maximumFractionDigits:9});
        let markup='<text x="12" y="18" font-size="11" fill="#555e50">Вдоль ствола</text><text x="105" y="18" font-size="12" fill="#555e50">'+spec.title+'</text>';
        for(let i=0;i<=5;i++){
          const depth=hole.total_depth_m*i/5,value=minimum+(maximum-minimum)*i/5;
          markup+=`<path d="M ${left} ${y(depth)} H ${left+width} M ${x(value)} ${top} V ${top+height}" stroke="#e4e1d7"/><text x="94" y="${y(depth)+4}" text-anchor="end" font-size="11" fill="#62675e">${number(depth)} м</text><text x="${x(value)}" y="286" text-anchor="middle" font-size="10" fill="#62675e">${number(Number((value*spec.axisFactor).toFixed(spec.signed?6:1)))}</text>`;
        }
        let previous;
        for(const row of rows){
          const rate=x(row[spec.field]),start=y(row.from_m),end=y(row.to_m);
          if(previous&&Math.abs(previous.to_m-row.from_m)<1e-6)markup+=`<path d="M ${x(previous[spec.field])} ${start} H ${rate}" stroke="${spec.color}" stroke-width="1.5"/>`;
          markup+=`<path data-${channel}-measurement="${escape(row.measurement_id)}" d="M ${rate} ${start} V ${end}" stroke="${spec.color}" stroke-width="2.5"><title>${escape(row.measurement_id)} · ${number(row.from_m)}–${number(row.to_m)} м · ${measured(row[spec.field])} ${spec.unit} ± ${measured(row[spec.sigma])}</title></path>`;
          previous=row;
        }
        element(prefix).innerHTML=markup;
        element(prefix+'Caption').textContent=`${number(rows.length)} измерений · максимум ${measured(peak)} ${spec.unit}`;
      }

      function drawProfile() {
        const hole = holes.find(item => item.hole_id === selectedHole);
        element('profileHole').value = selectedHole ?? '';
        element('profileAnalyte').disabled = !hole;
        drawBoreholeLogProfile(hole,'gamma');
        drawBoreholeLogProfile(hole,'magnetic');
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
        const maximum = Math.max(1e-9,...assays.map(row => row.result_value), observations.plan.analytes.find(item => item.analyte === analyte)?.detection_limit ?? 0);
        const target = drillingTargets.get(hole.hole_id);
        element('holeProfileTitle').textContent = target ? `${selectedHole} · ${drillingKinds[target.method].label} · ${target.observation_id}` : selectedHole;
        element('holeProfileCaption').textContent = `Устье X ${number(hole.x_m)} · Y ${number(hole.y_m)} м · ствол ${number(hole.total_depth_m)} м · угол ${number(hole.dip_deg)}° · азимут ${number(hole.azimuth_deg)}°`;
        let markup = '<text x="12" y="18" font-size="11" fill="#555e50">Вдоль ствола</text><text x="162" y="18" font-size="12" fill="#555e50">Описание керна</text><text x="380" y="18" font-size="12" fill="#555e50">Содержание по пробам</text>';
        for (let index = 0; index <= 5; index++) {
          const y = 36 + index * 46;
          markup += `<path d="M 105 ${y} H 640" stroke="#e4e1d7"/><text x="94" y="${y + 4}" text-anchor="end" font-size="11" fill="#62675e">${number(index * hole.total_depth_m / 5)} м</text>`;
        }
        for (const log of logs) {
          const color = rocks[log.observed_rock_id]?.color || '#b8b8a9';
          const y = 36 + log.from_m * scale, h = (log.to_m - log.from_m) * scale;
          markup += `<rect x="118" y="${y}" width="50" height="${h}" fill="${escape(color)}" stroke="white" stroke-width=".7"><title>${escape(log.observed_rock_name)} · ${number(log.from_m)}–${number(log.to_m)} м</title></rect>`;
          if (h > 13) markup += `<text x="180" y="${y + h / 2 + 4}" font-size="10" fill="#555e50">${escape(log.observed_rock_name)}</text>`;
        }
        for (const assay of assays) {
          const below = assay.result_qualifier === 'lt';
          const y = 36 + assay.from_m * scale, h = Math.max(.6, (assay.to_m - assay.from_m) * scale - .4);
          markup += `<rect x="${axisLeft}" y="${y}" width="${Math.max(1, assay.result_value / maximum * axisWidth)}" height="${h}" fill="${below ? '#b7c9d5' : '#168c86'}"><title>${number(assay.from_m)}–${number(assay.to_m)} м: ${below ? '&lt; ' : ''}${number(assay.result_value)} ${escape(assay.unit)}</title></rect>`;
        }
        markup += `<text x="${axisLeft}" y="286" font-size="10" fill="#62675e">0</text><text x="${axisLeft + axisWidth}" y="286" text-anchor="end" font-size="10" fill="#62675e">${number(maximum)} ${escape(observations.plan.analytes.find(item => item.analyte === analyte)?.unit ?? '')}</text>`;
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
      let updateFieldImportHint = () => {};
      function renderTable() {
        updateFieldImportHint();
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
        element('holeFilterLabel').classList.toggle('hidden', !fields.includes('hole_id'));
        element('sourceFilterLabel').classList.toggle('hidden', !fields.includes('hole_id') || !drillingSources.length);
        const sourceSelected = sourceByKind.has(element('observationSourceFilter').value);
        element('downloadDrillingSource').classList.toggle('hidden', !sourceSelected || !fields.includes('hole_id'));
        element('downloadObservationCsv').textContent = sourceSelected ? 'CSV источника' : 'CSV всей таблицы';
        element('trenchFilterLabel').classList.toggle('hidden', !fields.includes('trench_id'));
        element('analyteFilterLabel').classList.toggle('hidden', !fields.includes('analyte'));
        element('sampleFilterLabel').classList.toggle('hidden', !fields.includes('sample_id'));
        element('qcFilterLabel').classList.toggle('hidden', activeTable !== 'quality_control');
        page = renderObservationRows('observation', fields, rows, page, 'Нет наблюдений для выбранных фильтров');
      }
      function renderObservationRows(prefix, fields, rows, requestedPage, emptyMessage) {
        const page = Math.max(0, Math.min(requestedPage, Math.ceil(rows.length / pageSize) - 1));
        element(prefix + 'TableHead').innerHTML = '<tr>' + fields.map(field => `<th scope="col" title="${escape(field)}">${escape(fieldNames[field] || field)}</th>`).join('') + '</tr>';
        element(prefix + 'TableBody').innerHTML = rows.slice(page * pageSize, (page + 1) * pageSize).map(row => '<tr>' + fields.map(field => {
          const value = row[field];
          const display = value === null || value === undefined || value === '' ? '—' : typeof value === 'number' ? ((field==='magnetic_susceptibility_si'||field==='magnetic_sigma_si')?value.toLocaleString('ru-RU',{maximumFractionDigits:9}):number(value)) : categoryNames[value] || value;
          return `<td>${escape(display)}</td>`;
        }).join('') + '</tr>').join('') || `<tr><td colspan="${fields.length}">${emptyMessage}</td></tr>`;
        element(prefix + 'Count').textContent = `${number(rows.length)} записей`;
        element(prefix + 'PageInfo').textContent = rows.length ? `${page * pageSize + 1}–${Math.min(rows.length, (page + 1) * pageSize)} из ${number(rows.length)} · пустые значения обозначены «—»` : 'Нет записей';
        element(prefix + 'Previous').disabled = page === 0;
        element(prefix + 'Next').disabled = (page + 1) * pageSize >= rows.length;
        return page;
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
      updateFieldImportHint=setupImportControls('field',()=>activeTable,
        ()=>element('fieldImportWhole').checked?Object.keys(observations.table_fields):activeSection==='boreholes'?ObservationImport.boreholeTables:sections[activeSection].tables,
        ()=>element('fieldImportWhole').checked?'':element('observationSourceFilter').value);
      refreshFieldwork=()=>{
        for(const rock of observations.rock_catalog)rocks[rock.id]=rock;
        drawExpeditionMetrics();refreshSourceOptions();updateSourceHoles();
        refreshFieldMethodRecords();page=0;renderTable();
      };
      renderRecognition(RECOGNITION_DATA);
    })(OBSERVATION_DATA ?? MANUAL_OBSERVATION_DATA);
'''

WORKSPACE_STYLES += METHODS_STYLES
WORKSPACE_PANELS = WORKSPACE_PANELS.replace('__PRELIMINARY_METHODS__', PRELIMINARY_METHODS_HTML).replace('__FIELD_METHODS__', FIELD_METHODS_HTML)
WORKSPACE_SCRIPT = WORKSPACE_SCRIPT.replace('__METHODS_SCRIPT__', METHODS_SCRIPT)
WORKSPACE_SCRIPT = WORKSPACE_SCRIPT.replace('__PRELIMINARY_SCRIPT__', PRELIMINARY_SCRIPT)

WORKSPACE_STYLES += RECONSTRUCTION_STYLES
WORKSPACE_PANELS = WORKSPACE_PANELS.replace("__RECONSTRUCTION_HTML__", RECONSTRUCTION_HTML).replace("__MINERALS_PANEL__", MINERALS_PANEL)
WORKSPACE_SCRIPT = WORKSPACE_SCRIPT.replace("__RECONSTRUCTION_SCRIPT__", RECONSTRUCTION_SCRIPT)

WORKSPACE_STYLES += IMPORT_STYLES
WORKSPACE_PANELS = WORKSPACE_PANELS.replace('__PRELIMINARY_IMPORT__', import_panel('preliminary')).replace('__FIELD_IMPORT__', import_panel('field'))
WORKSPACE_SCRIPT = WORKSPACE_SCRIPT.replace('__IMPORT_ENGINE__', IMPORT_ENGINE).replace('__IMPORT_UI__', IMPORT_UI)
