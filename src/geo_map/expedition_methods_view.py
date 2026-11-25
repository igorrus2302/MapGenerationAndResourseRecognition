"""Preliminary survey and fieldwork panels built from public observations."""

METHODS_STYLES = r'''
    .method-sections { display: flex; flex-wrap: wrap; align-items: stretch; gap: 6px; margin: 0 0 18px; }
    .method-section { width: auto; min-height: 40px; padding: 9px 16px; font-size: 13px; }
    .method-section[aria-pressed="true"] { color: white; background: var(--accent); border-color: var(--accent); }
    .method-section[aria-pressed="true"]:hover { background: var(--accent-hover); color: white; }
    .method-overview { margin-bottom: 16px; }
    .method-overview p { color: var(--muted); font-size: 12px; line-height: 1.7; }
    .method-map { width: 100%; height: 300px; display: block; }
    .method-toolbar { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
    .method-toolbar select { width: auto; max-width: min(100%, 260px); }
    .method-profile { width: 100%; height: 190px; display: block; }
    .data-downloads { display: flex; gap: 8px; flex-wrap: wrap; align-items: stretch; }
    .data-downloads button { width: auto; }
    .data-filters input { display: block; width: 100%; min-height: 38px; border: 1px solid var(--line); border-radius: 3px; margin-top: 5px; padding: 7px 10px; background: var(--surface); color: var(--text); font: inherit; }
    .qc-metrics { display: flex; flex-wrap: wrap; gap: 1px; border: 1px solid var(--line); background: var(--line); margin: 18px 0; }
    .qc-metrics span { flex: 1 1 145px; padding: 12px 16px; background: var(--surface); color: var(--ink); font-size: 13px; }
    .qc-metrics b { font-size: 23px; margin-right: 8px; font-variant-numeric: tabular-nums; }
    .qc-metrics .qc-fail { background: #f6e6df; color: #a93e2b; }
    .qc-metrics .qc-warning { background: #f5edda; color: #765719; }
'''

FIELD_METHODS_HTML = r'''
      <div id="surfaceOverview" class="panel-card method-overview hidden">
        <h3>Поверхностная геохимия</h3><div class="muted" id="surfaceCaption"></div>
        <div class="selection-controls"><label>Почвенная проба<select id="surfaceSampleSelect"></select></label><label>Компонент<select id="surfaceMapAnalyte"></select></label></div>
        <svg id="surfaceMap" class="method-map" viewBox="0 0 650 300" role="group" aria-label="Измеренные содержания в почвенных пробах"></svg>
        <p id="surfaceMapLegend"></p>
        <div id="surfaceSampleDetail" class="selection-detail" aria-live="polite"></div>
      </div>
      <div id="trenchOverview" class="panel-card method-overview hidden">
        <h3>Траншейные наблюдения</h3><div id="trenchCaption" class="muted" aria-live="polite"></div>
        <div class="selection-controls"><label>Траншея<select id="trenchSelect"></select></label></div>
        <svg id="trenchMap" class="method-map" viewBox="0 0 650 300" role="group" aria-label="Положение наблюдённых траншей"></svg>
        <div class="method-toolbar"><h3>Описание дна и канавные пробы</h3><select id="trenchProfileAnalyte" aria-label="Компонент канавных проб"></select></div>
        <svg id="trenchProfile" class="method-profile" viewBox="0 0 700 180" role="img" aria-label="Наблюдённые породы и результаты проб вдоль траншеи"></svg>
        <p>Показан материал, вскрытый на заданной глубине. При мощной почве неглубокая траншея описывает почву. Пробы отбираются полосой у дна; серые результаты — ниже предела обнаружения.</p>
      </div>
      <div id="structureOverview" class="panel-card method-overview hidden">
        <h3>Наблюдённые структуры</h3><div id="structureMetrics" class="qc-metrics"></div>
        <p id="structureCaption"></p>
      </div>
      <div id="qualityOverview" class="panel-card method-overview hidden">
        <h3>Контроль качества анализов</h3><div id="qualityMetrics" class="qc-metrics"></div>
        <p id="qualityCaption"></p>
        <p>Дубликаты сравниваются с измеренными исходными пробами, стандарты — с известным контрольным содержанием, холостые пробы — с абсолютным допуском. При цензурировании результата численная оценка может быть недоступна. Эти проверки не подтверждают каждый отдельный первичный анализ.</p>
      </div>
'''

PRELIMINARY_METHODS_HTML = r'''
      <div class="panel-card method-overview">
        <h3>Просмотр отдельных наблюдений</h3>
        <div class="selection-controls"><label>Точка наблюдения<select id="preliminaryPointFilter"></select></label></div>
        <div id="preliminaryPointDetail" class="selection-detail" aria-live="polite"></div>
      </div>
      <div id="outcropOverview" class="panel-card method-overview hidden">
        <h3>Наблюдённые обнажения</h3>
        <div class="muted" id="outcropCaption"></div>
        <svg id="outcropMap" class="method-map" viewBox="0 0 650 300" role="group" aria-label="Точки наблюдения обнажений"></svg>
      </div>
      <div id="terrainSurveyOverview" class="panel-card method-overview hidden">
        <h3>Типы рельефа по съёмке высот</h3>
        <div class="muted" id="terrainSurveyCaption"></div>
        <svg id="terrainSurveyMap" class="method-map" viewBox="0 0 650 300" role="group" aria-label="Типы рельефа в точках съёмки"></svg>
        <p id="terrainSurveyLegend"></p>
      </div>
      <div id="geophysicalOverview" class="panel-card method-overview hidden">
        <h3 id="geophysicalHeading"></h3>
        <div id="geophysicalCaption" class="muted"></div>
        <svg id="geophysicalMap" class="method-map" viewBox="0 0 650 300" role="group" aria-label="Значения геофизической съёмки"></svg>
      </div>
'''

METHODS_SCRIPT = r'''
      Object.assign(fieldNames, {
        trench_id: 'Траншея', start_x_m: 'Начало X, м', start_y_m: 'Начало Y, м', end_x_m: 'Конец X, м', end_y_m: 'Конец Y, м', width_m: 'Ширина, м', surveyed_length_m: 'Длина, м', trench_status: 'Состояние', survey_date: 'Дата съёмки',
        sample_date: 'Дата отбора', sample_material: 'Материал', sampling_depth_from_m: 'Глубина отбора от, м', sampling_depth_to_m: 'Глубина отбора до, м', sampling_method: 'Способ отбора', parent_sample_id: 'Исходная проба',
        control_id: 'Контроль', sample_source: 'Источник пробы', reference_value: 'Контрольное значение', reference_uncertainty: 'Неопределённость стандарта', absolute_difference: 'Абсолютное отклонение', relative_difference_percent: 'Относительное отклонение, %', acceptance_limit: 'Допуск', acceptance_unit: 'Единица допуска', surface_elevation_m: 'Отметка поверхности, м'
      });
      Object.assign(categoryNames, {fault: 'Зона разлома', oriented_core: 'Ориентированный керн', duplicate: 'Дубликат', blank: 'Холостая', standard: 'Стандарт', pass: 'В пределах допуска', warning: 'Предупреждение', fail: 'Вне допуска', soil: 'Почва', rock: 'Порода', regolith: 'Рыхлый смешанный материал', channel: 'Канавное', grid_soil_sample: 'Почвенное по сетке', soil_sample: 'Почвенное', borehole: 'Скважина', surface: 'Поверхность', trench: 'Траншея', laboratory: 'Лаборатория'});
      const sections = {
        boreholes: {label: 'Скважины', panel: 'boreholeOverview', tables: ['borehole_collars', 'borehole_lithology', 'borehole_assays', 'downhole_properties']},
        surface: {label: 'Геохимия', panel: 'surfaceOverview', tables: ['surface_geochemistry'], geojson: 'surface_geochemistry'},
        trenches: {label: 'Траншеи', panel: 'trenchOverview', tables: ['trenches', 'trench_intervals', 'trench_samples'], geojson: 'trench_paths'},
        structures: {label: 'Структуры', panel: 'structureOverview', tables: ['structural_observations', 'fault_intersections']},
        quality: {label: 'Контроль качества', panel: 'qualityOverview', tables: ['quality_control']}
      };
      if (observations.table_fields.downhole_gamma) sections.boreholes.tables.push('downhole_gamma');
      if (observations.table_fields.downhole_magnetic) sections.boreholes.tables.push('downhole_magnetic');
      const sectionButtons = addMethodButtons(sections, 'expeditionSections', activateSection);
      let activeSection = 'boreholes';
      const trenches = tables.trenches || [];
      let selectedTrench = trenches[0]?.trench_id;
      function activateSection(key) {
        activeSection = key;
        for (const [name, section] of Object.entries(sections)) {
          element(section.panel).classList.toggle('hidden', name !== key);
          sectionButtons[name].setAttribute('aria-pressed', String(name === key));
        }
        for (const id of ['observationSourceFilter', 'observationHoleFilter', 'observationTrenchFilter', 'observationAnalyteFilter', 'observationSampleFilter', 'observationQcFilter', 'surfaceSampleSelect']) element(id).value = '';
        updateSourceHoles();
        if (key === 'surface') drawSurface();
        page = 0; buildTableTabs(sections[key].tables);
        element('dataSectionTitle').textContent = sections[key].label;
        element('downloadMethodGeoJson').classList.toggle('hidden', !sections[key].geojson);
        renderTable();
      }
      element('downloadMethodGeoJson').addEventListener('click', () => downloadGeoJson(sections[activeSection].geojson));
      element('observationQcFilter').addEventListener('change', () => { page = 0; renderTable(); });
      element('observationTrenchFilter').addEventListener('change', () => {
        const id = element('observationTrenchFilter').value;
        if (id) selectTrench(id);
        else { page = 0; renderTable(); }
      });
      element('observationSampleFilter').addEventListener('input', () => {
        if (activeSection === 'surface') {
          const id = element('observationSampleFilter').value.trim();
          element('surfaceSampleSelect').value = surfaceSamples.has(id) ? id : '';
          drawSurface();
        }
        page = 0; renderTable();
      });
      element('observationTrenchFilter').innerHTML = '<option value="">Все траншеи</option>' + trenches.map(row => `<option value="${escape(row.trench_id)}">${escape(row.trench_id)}</option>`).join('');

      const surfaceAnalytes = observations.plan.methods?.surface_geochemistry?.analytes || [];
      const surfaceOptions=()=>[...new Map([...surfaceAnalytes,...(tables.surface_geochemistry||[])].map(item=>[item.analyte,item])).values()];
      const surfaceSamples = new Map((tables.surface_geochemistry || []).map(row => [row.sample_id, row]));
      element('surfaceSampleSelect').innerHTML = '<option value="">Все почвенные пробы</option>' + [...surfaceSamples.keys()].map(id => `<option value="${escape(id)}">${escape(id)}</option>`).join('');
      element('surfaceSampleSelect').disabled = !surfaceSamples.size;
      element('surfaceMapAnalyte').innerHTML = surfaceOptions().map(item => `<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');
      function drawSurface() {
        const analyte = element('surfaceMapAnalyte').value;
        const selected = element('surfaceSampleSelect').value;
        const rows = (tables.surface_geochemistry || []).filter(row => row.analyte === analyte);
        const values = rows.filter(row => row.result_qualifier !== 'lt').map(row => row.result_value);
        const minimum = values.length ? Math.min(...values) : 0, maximum = values.length ? Math.max(...values) : 0;
        const frame = mapFrame();
        let markup = frame.markup;
        for (const row of rows) {
          const point = frame.point(row.x_m, row.y_m);
          const below = row.result_qualifier === 'lt';
          const strength = maximum === minimum ? .5 : (row.result_value - minimum) / (maximum - minimum);
          const color = below ? '#b7c9d5' : `hsl(${190 - 170 * strength}, 65%, 48%)`;
          const current = row.sample_id === selected;
          markup += `<circle class="hole-dot" role="button" tabindex="0" aria-label="${escape(row.sample_id)}" aria-pressed="${current}" data-sample="${escape(row.sample_id)}" cx="${point.x}" cy="${point.y}" r="${current ? 7 : 5}" fill="${color}" stroke="${current ? '#a35a35' : 'white'}" stroke-width="${current ? 3 : 1}"><title>${escape(row.sample_id)}: ${below ? '&lt; ' : ''}${number(row.result_value)} ${escape(row.unit)}</title></circle>`;
        }
        element('surfaceMap').innerHTML = markup;
        element('surfaceCaption').textContent = `${summary.surface_sample_count || 0} почвенных проб · нажмите на точку для просмотра её анализов`;
        element('surfaceMapLegend').textContent = !rows.length ? 'Поверхностная геохимия выключена или данные отсутствуют.' : values.length ? `Цвет отражает измеренное содержание: ${number(minimum)}–${number(maximum)} ${rows[0].unit}. Серые точки — ниже предела обнаружения.` : 'Все результаты ниже предела обнаружения. Показаны серым цветом.';
        const sample = surfaceSamples.get(selected);
        const measurement = rows.find(row => row.sample_id === selected);
        element('surfaceSampleDetail').textContent = sample ? `${selected} · X ${number(sample.x_m)}, Y ${number(sample.y_m)} м · ${measurement ? analyte + ': ' + (measurement.result_qualifier === 'lt' ? '< ' : '') + number(measurement.result_value) + ' ' + measurement.unit : 'нет измерения по выбранному компоненту'}` : 'Выберите пробу из списка или нажмите на точку карты.';
      }
      function selectSurfaceSample(id) {
        if (id && !surfaceSamples.has(id)) return;
        element('surfaceSampleSelect').value = id;
        element('observationSampleFilter').value = id;
        page = 0; drawSurface(); renderTable();
      }
      function selectSurface(event) {
        const dot = event.target.closest('[data-sample]');
        if (!dot) return;
        selectSurfaceSample(dot.dataset.sample);
      }
      element('surfaceSampleSelect').addEventListener('change', () => selectSurfaceSample(element('surfaceSampleSelect').value));
      element('surfaceMap').addEventListener('click', selectSurface);
      element('surfaceMap').addEventListener('keydown', event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); selectSurface(event); } });
      element('surfaceMapAnalyte').addEventListener('change', drawSurface);

      element('trenchSelect').innerHTML = trenches.map(row => `<option value="${escape(row.trench_id)}">${escape(row.trench_id)}</option>`).join('');
      element('trenchSelect').disabled = !trenches.length;
      element('trenchProfileAnalyte').innerHTML = analyteOptions;
      function drawTrenches() {
        const frame = mapFrame();
        let markup = frame.markup;
        for (const trench of trenches) {
          const start = frame.point(trench.start_x_m, trench.start_y_m), end = frame.point(trench.end_x_m, trench.end_y_m);
          markup += `<line class="hole-dot" role="button" tabindex="0" aria-label="${escape(trench.trench_id)}" data-trench="${escape(trench.trench_id)}" x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="${trench.trench_id === selectedTrench ? '#a35a35' : '#355d48'}" stroke-width="7" stroke-linecap="round"><title>${escape(trench.trench_id)} · ${number(trench.surveyed_length_m)} м</title></line>`;
        }
        element('trenchMap').innerHTML = markup;
        const trench = trenches.find(row => row.trench_id === selectedTrench);
        if (!trench) {
          element('trenchCaption').textContent = 'Траншейные наблюдения выключены или данные отсутствуют.';
          element('trenchProfile').innerHTML = '';
          return;
        }
        element('trenchCaption').textContent = `${selectedTrench} · длина ${number(trench.surveyed_length_m)} м · глубина ${number(trench.depth_m)} м · ширина ${number(trench.width_m)} м`;
        const logs = (tables.trench_intervals || []).filter(row => row.trench_id === selectedTrench);
        const assays = (tables.trench_samples || []).filter(row => row.trench_id === selectedTrench && row.analyte === element('trenchProfileAnalyte').value);
        const scale = 600 / trench.surveyed_length_m;
        const maximum = Math.max(0, ...assays.map(row => row.result_value));
        let profile = '<text x="50" y="20" font-size="11" fill="#555e50">Наблюдённые породы у дна</text>';
        for (const log of logs) profile += `<rect x="${50 + log.from_m * scale}" y="30" width="${(log.to_m - log.from_m) * scale}" height="27" fill="${escape(rocks[log.observed_rock_id]?.color || '#b7c9d5')}"><title>${escape(log.observed_rock_name)} · ${number(log.from_m)}–${number(log.to_m)} м</title></rect>`;
        for (const row of assays) {
          const h = Math.max(1, row.result_value / (maximum || 1) * 65);
          profile += `<rect x="${50 + row.from_m * scale}" y="${135 - h}" width="${Math.max(.5, (row.to_m - row.from_m) * scale - .5)}" height="${h}" fill="${row.result_qualifier === 'lt' ? '#b7c9d5' : '#168c86'}"><title>${number(row.from_m)}–${number(row.to_m)} м: ${row.result_qualifier === 'lt' ? '&lt; ' : ''}${number(row.result_value)} ${escape(row.unit)}</title></rect>`;
        }
        profile += `<text x="50" y="160" font-size="11" fill="#62675e">0 м</text><text x="650" y="160" text-anchor="end" font-size="11" fill="#62675e">${number(trench.surveyed_length_m)} м · ${assays.length ? `максимум ${number(maximum)} ${escape(assays[0].unit)}` : 'нет результатов проб'}</text>`;
        element('trenchProfile').innerHTML = profile;
      }
      function selectTrench(identifier) {
        if (!trenches.some(row => row.trench_id === identifier)) return;
        selectedTrench = identifier; element('trenchSelect').value = identifier;
        element('observationTrenchFilter').value = identifier; page = 0; drawTrenches(); renderTable();
      }
      element('trenchSelect').addEventListener('change', () => selectTrench(element('trenchSelect').value));
      element('trenchProfileAnalyte').addEventListener('change', drawTrenches);
      element('trenchMap').addEventListener('click', event => { const target = event.target.closest('[data-trench]'); if (target) selectTrench(target.dataset.trench); });
      element('trenchMap').addEventListener('keydown', event => { if (!['Enter', ' '].includes(event.key)) return; const target = event.target.closest('[data-trench]'); if (target) { event.preventDefault(); selectTrench(target.dataset.trench); } });

      function drawStructureAndQuality() {
      const structures = tables.structural_observations || [];
      const oriented = structures.filter(row => row.feature_type === 'fault' && row.strike_deg !== null).length;
      element('structureMetrics').innerHTML = [[summary.contact_count, 'контактов'], [summary.fault_observation_count || 0, 'зон нарушений'], [oriented, 'определений ориентации']].map(([value, label]) => `<span><b>${number(value)}</b>${label}</span>`).join('');
      element('structureCaption').textContent = 'Каждая запись относится к наблюдению в скважине. Интервалы нарушенных пород связаны с записями разломов по идентификатору наблюдения. Ориентация доступна при ориентированном керне; положение разлома за пределами наблюдённого участка не задано.';
      const controls = tables.quality_control || [];
      element('qualityMetrics').innerHTML = [['pass', 'в допуске'], ['warning', 'предупреждений'], ['fail', 'вне допуска'], ['not_checked', 'не оценено']].map(([flag, label]) => `<span class="qc-${flag}"><b>${number(controls.filter(row => row.qc_flag === flag).length)}</b>${label}</span>`).join('');
      element('qualityCaption').textContent = `${summary.qc_sample_count || 0} контрольных проб · ${summary.qc_result_count || 0} результатов. Дубликаты, холостые пробы и стандарты отбираются по заданному плану лабораторного контроля.`;
      }
      function refreshFieldMethodRecords() {
        const sampleSelect=element('surfaceSampleSelect'), selectedSample=sampleSelect.value;
        surfaceSamples.clear();
        for(const row of tables.surface_geochemistry||[])surfaceSamples.set(row.sample_id,row);
        sampleSelect.innerHTML='<option value="">Все почвенные пробы</option>'+[...surfaceSamples.keys()].map(id=>`<option value="${escape(id)}">${escape(id)}</option>`).join('');
        sampleSelect.value=surfaceSamples.has(selectedSample)?selectedSample:'';
        sampleSelect.disabled=!surfaceSamples.size;
        const analyteSelect=element('surfaceMapAnalyte'), oldAnalyte=analyteSelect.value, options=surfaceOptions();
        analyteSelect.innerHTML=options.map(item=>`<option value="${escape(item.analyte)}">${escape(item.analyte)} · ${escape(item.unit)}</option>`).join('');
        if(options.some(item=>item.analyte===oldAnalyte))analyteSelect.value=oldAnalyte;
        const trenchFilter=element('observationTrenchFilter'), previous=trenchFilter.value;
        const trenchOptions=trenches.map(row=>`<option value="${escape(row.trench_id)}">${escape(row.trench_id)}</option>`).join('');
        trenchFilter.innerHTML='<option value="">Все траншеи</option>'+trenchOptions;
        trenchFilter.value=trenches.some(row=>row.trench_id===previous)?previous:'';
        if(!trenches.some(row=>row.trench_id===selectedTrench))selectedTrench=trenches[0]?.trench_id;
        element('trenchSelect').innerHTML=trenchOptions;
        element('trenchSelect').value=selectedTrench??'';
        element('trenchSelect').disabled=!trenches.length;
        drawSurface();drawTrenches();drawStructureAndQuality();
      }
      drawStructureAndQuality();
      drawSurface(); drawTrenches(); activateSection('boreholes');
'''
