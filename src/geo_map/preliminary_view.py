"""Collect and display preliminary survey records in the offline viewer."""

PRELIMINARY_SCRIPT = r'''
      Object.assign(fieldNames, {
        survey_date: 'Дата съёмки', surface_elevation_m: 'Отметка поверхности, м', station_id: 'Станция съёмки',
        elevation_uncertainty_m: 'Погрешность высоты, м', slope_deg: 'Уклон, °',
        local_relief_m: 'Относительная высота, м', terrain_type: 'Тип рельефа',
        magnetic_anomaly_nt: 'Магнитная аномалия, нТл', magnetic_sigma_nt: 'Погрешность магнитного канала, нТл',
        gamma_count_rate_cps: 'Гамма-фон, имп/с', gamma_sigma_cps: 'Погрешность гамма-канала, имп/с'
      });
      Object.assign(categoryNames, {
        surface_mapping: 'Осмотр поверхности', grid_elevation_survey: 'Съёмка высот по сетке',
        ground_geophysical_survey: 'Наземная геофизическая съёмка'
      });
      for (const [code, type] of Object.entries(terrainTypes)) categoryNames[code] = type.label;
      const surveyChannels = {magnetic_observations: 'magnetic', gamma_observations: 'gamma'};

      function roundMeasurement(value, decimals) {
        // Follow Python's ties-to-even rule for exactly representable halfway values.
        const halfway = Math.abs(value) * 2 ** (decimals + 1);
        if (Number.isSafeInteger(halfway) && halfway % 4 === 1) {
          const lower = (BigInt(halfway) * 5n ** BigInt(decimals) - 1n) / 2n;
          return Math.sign(value) * Number(`${lower}e-${decimals}`);
        }
        return Number(value.toFixed(decimals));
      }

      function collectSurvey(plan) {
        const result = {};
        const {terrain_survey: terrainSurvey, outcrops} = plan.methods;
        const exactCells = new Map(cells.map(cell => [cell.y_index * dims.width_cells + cell.x_index, cell]));
        const sampled = point => {
          const [x, y] = point.position.map(coordinate => Math.floor(coordinate / dims.cell_size_m));
          return exactCells.get(y * dims.width_cells + x);
        };
        const elevation = cell => cell.surface_elevation_m ?? 0;
        const record = (point, method) => ({
          campaign_id: plan.campaign_id, observation_id: point.observation_id, x_m: point.x_m, y_m: point.y_m,
          observation_method: method, survey_date: plan.date
        });
        for (const [table, method] of Object.entries(surveyChannels)) {
          const settings = plan.methods[table];
          if (!settings) continue;
          const {field, sigma_field: sigmaField, sigma, counting_time_s: countingTime, position_uncertainty_m: positionSigma} = settings;
          result[table] = settings.points.map(point => {
            const cell = sampled(point);
            const expected = cell.geophysical_fields[field];
            const uncertainty = countingTime ? Math.sqrt(sigma ** 2 + expected / countingTime) : sigma;
            const value = expected + point.standard_error * uncertainty;
            return {
              ...record(point, 'ground_geophysical_survey'), station_id: point.station_id,
              surface_elevation_m: elevation(cell), [field]: roundMeasurement(method === 'gamma' ? Math.max(0, value) : value, 4),
              [sigmaField]: countingTime ? roundMeasurement(uncertainty, 4) : sigma, position_uncertainty_m: positionSigma
            };
          });
        }
        if (terrainSurvey) {
          const {columns, rows, points, slope_threshold_deg: slopeLimit, local_relief_threshold_m: reliefLimit} = terrainSurvey;
          const heights = points.map(point => roundMeasurement(elevation(sampled(point)) + point.elevation_error_m, 3));
          const at = (x, y) => x < 0 || x >= columns || y < 0 || y >= rows ? undefined : heights[y * columns + x];
          const axes = [[1, 0, dims.width_m / columns], [0, 1, dims.height_m / rows]];
          result.terrain_observations = points.map((point, index) => {
            const x = index % columns, y = Math.floor(index / columns);
            const height = heights[index], gradients = [], references = [];
            for (const [dx, dy, step] of axes) {
              const before = at(x - dx, y - dy), after = at(x + dx, y + dy);
              if (before !== undefined && after !== undefined) {
                gradients.push((after - before) / (2 * step));
                const farBefore = at(x - 2 * dx, y - 2 * dy), farAfter = at(x + 2 * dx, y + 2 * dy);
                references.push(farBefore !== undefined && farAfter !== undefined
                  ? (farBefore + farAfter) / 2 : (before + after) / 2);
              } else if (before !== undefined) {
                gradients.push((height - before) / step);
              } else if (after !== undefined) {
                gradients.push((after - height) / step);
              }
            }
            const slope = gradients.length ? roundMeasurement(Math.atan(Math.hypot(...gradients)) * (180 / Math.PI), 3) : null;
            const relief = references.length ? roundMeasurement(height - references.reduce((sum, value) => sum + value, 0) / references.length, 3) : null;
            let type = 'flat';
            if (slope === null) type = 'undetermined';
            else if (slope >= slopeLimit) type = 'slope';
            else if (relief !== null && relief >= reliefLimit) type = 'hill';
            else if (relief !== null && relief <= -reliefLimit) type = 'depression';
            return {
              ...record(point, 'grid_elevation_survey'), surface_elevation_m: height,
              elevation_uncertainty_m: terrainSurvey.elevation_uncertainty_m,
              slope_deg: slope, local_relief_m: relief, terrain_type: type
            };
          });
        }
        if (outcrops) {
          const cover = terrain?.surface_cover_rock_id ?? 'soil';
          result.outcrop_observations = outcrops.points.flatMap(point => {
            const cell = sampled(point), rock = cell.intervals[0].rock_id;
            if (rock === cover) return [];
            return [{
              ...record(point, 'surface_mapping'), surface_elevation_m: elevation(cell),
              observed_rock_id: rock, observed_rock_name: rockById[rock].name,
              position_uncertainty_m: outcrops.position_uncertainty_m
            }];
          });
        }
        return result;
      }

      function surveyGeoJson(name, rows) {
        return {
          type: 'FeatureCollection', schema_version: '1.0', name, coordinate_system: 'local_cartesian',
          coordinate_unit: 'm', map_extent_m: {x: [0, dims.width_m], y: [0, dims.height_m]},
          features: rows.map(({x_m, y_m, ...properties}) => ({
            type: 'Feature', id: properties.observation_id, geometry: {type: 'Point', coordinates: [x_m, y_m]}, properties
          }))
        };
      }

      function drawPreliminaryMap(method, rows, settings, selectedId) {
        const {point, markup} = mapFrame(dims);
        const radius = Math.max(1.25, Math.min(4.25, 85 / Math.sqrt(rows.length || 1)));
        const selectedRow = rows.find(row => row.observation_id === selectedId);
        const points = selectedRow ? [...rows.filter(row => row !== selectedRow), selectedRow] : rows;
        const attributes = (row, x, y, size, border = 'none') => {
          const selected = row.observation_id === selectedId;
          return `class="hole-dot" role="button" tabindex="0" aria-label="${escape(row.observation_id)}" aria-pressed="${selected}" data-observation="${escape(row.observation_id)}" cx="${x}" cy="${y}" r="${selected ? Math.max(6, size + 2) : size}" stroke="${selected ? '#e95e2a' : border}" stroke-width="${selected ? 3 : 1}"`;
        };
        if (method === 'outcrops') {
          element('outcropMap').innerHTML = markup + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const color = rockById[row.observed_rock_id]?.color || '#1677a8';
            return `<circle ${attributes(row, x, y, 4.5, '#243b53')} fill="${escape(color)}"><title>${escape(row.observation_id)} · ${escape(row.observed_rock_name)} · ${number(row.surface_elevation_m)} м</title></circle>`;
          }).join('');
          element('outcropCaption').textContent = `${number(rows.length)} обнажений на ${number(settings.points?.length ?? settings.point_count)} обследованных точках. Цвет соответствует наблюдённой породе.`;
        } else if (method === 'terrain_survey') {
          const counts = new Map();
          element('terrainSurveyMap').innerHTML = markup + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const type = terrainTypes[row.terrain_type] || terrainTypes.undetermined;
            counts.set(type.label, (counts.get(type.label) || 0) + 1);
            return `<circle ${attributes(row, x, y, radius)} fill="${type.color}"><title>${escape(row.observation_id)} · ${type.label} · ${number(row.surface_elevation_m)} м</title></circle>`;
          }).join('');
          element('terrainSurveyCaption').textContent = `${number(rows.length)} точек · порог уклона ${number(settings.slope_threshold_deg)}° · порог относительной высоты ${number(settings.local_relief_threshold_m)} м`;
          element('terrainSurveyLegend').innerHTML = Object.values(terrainTypes).filter(type => counts.has(type.label))
            .map(type => `<span style="color:${type.color}">● ${type.label} · ${number(counts.get(type.label))}</span>`).join(' &nbsp; ');
        } else {
          const {field, label, unit} = geophysicalChannels[surveyChannels[method]];
          element('geophysicalHeading').textContent = label;
          const values = rows.map(row => row[field]);
          const minimum = Math.min(...values), maximum = Math.max(...values);
          element('geophysicalMap').innerHTML = markup + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const scaled = minimum === maximum ? .5 : (row[field] - minimum) / (maximum - minimum);
            return `<circle ${attributes(row, x, y, radius)} fill="${geophysicalColor(scaled)}"><title>${escape(row.observation_id)} · ${label} ${number(row[field])} ${unit}</title></circle>`;
          }).join('');
          element('geophysicalCaption').textContent = rows.length
            ? `${number(rows.length)} точек · от ${number(minimum)} ${unit} (синий) до ${number(maximum)} ${unit} (оранжевый)`
            : 'Для этого канала пока нет измерений.';
        }
      }

      function initPreliminary() {
        const plan = PRELIMINARY_PLAN;
        const settings = plan?.methods ?? observations?.plan?.methods ?? {};
        const tableFields = plan?.table_fields ?? observations?.table_fields ?? {};
        const definitions = {
          magnetic_observations: {label: 'Магнитное поле', panel: 'geophysicalOverview', table: 'magnetic_observations',
            title: 'Магнитные наблюдения', archiveSetting: 'geophysical_survey'},
          gamma_observations: {label: 'Гамма-фон', panel: 'geophysicalOverview', table: 'gamma_observations',
            title: 'Радиометрические наблюдения', archiveSetting: 'geophysical_survey'},
          terrain_survey: {label: 'Рельеф', panel: 'terrainSurveyOverview', table: 'terrain_observations', title: 'Точки съёмки рельефа'},
          outcrops: {label: 'Обнажения', panel: 'outcropOverview', table: 'outcrop_observations', title: 'Наблюдения обнажений'}
        };
        const methods = Object.fromEntries(Object.entries(definitions).filter(([key, {table, archiveSetting}]) =>
          (plan ? settings[key] : settings[archiveSetting ?? key]?.enabled) && tableFields[table]));
        const keys = Object.keys(methods);
        const start = element('collectPreliminary');
        const status = element('preliminaryStatus');
        if (!keys.length) {
          start.classList.add('hidden');
          status.textContent = 'Для этой карты сбор предварительных наблюдений отключён в настройках.';
          return;
        }
        start.addEventListener('click', () => {
          if (start.disabled) return;
          start.disabled = true;
          let results;
          try {
            results = plan ? collectSurvey(plan) : observations.tables;
          } catch {
            start.disabled = false;
            status.textContent = 'Не удалось собрать наблюдения по этой карте. Попробуйте ещё раз.';
            return;
          }
          let active, page = 0;
          const selectedPoints = new Map();
          const pointFilter = element('preliminaryPointFilter');
          const buttons = addMethodButtons(methods, 'preliminarySections', activate);
          const activeTable = () => methods[active].table;
          const activeRows = () => results[activeTable()] || [];
          const selectedPoint = () => selectedPoints.get(active) ?? '';
          const selectedRow = () => activeRows().find(row => row.observation_id === selectedPoint());
          function renderTable() {
            const rows = selectedPoint() ? activeRows().filter(row => row.observation_id === selectedPoint()) : activeRows();
            page = renderObservationRows('preliminary', tableFields[activeTable()], rows,
                                         page, 'Для этого раздела пока нет наблюдений');
          }
          function renderMap() {
            drawPreliminaryMap(active, activeRows(), settings[active] ?? settings[methods[active].archiveSetting], selectedPoint());
            const row = selectedRow();
            const detailFields = {
              magnetic_observations: ['magnetic_anomaly_nt', 'magnetic_sigma_nt'],
              gamma_observations: ['gamma_count_rate_cps', 'gamma_sigma_cps'],
              terrain_survey: ['terrain_type', 'surface_elevation_m', 'slope_deg', 'local_relief_m'],
              outcrops: ['observed_rock_name', 'surface_elevation_m']
            };
            element('preliminaryPointDetail').innerHTML = row
              ? `<strong>${escape(row.observation_id)}</strong> · X ${number(row.x_m)}, Y ${number(row.y_m)} м · ` + detailFields[active].map(field => {
                const value = row[field];
                const display = value == null ? '—' : typeof value === 'number' ? number(value) : categoryNames[value] || value;
                return `${escape(fieldNames[field] || field)}: ${escape(display)}`;
              }).join(' · ')
              : activeRows().length ? 'Выберите точку из списка или нажмите на карту. Полный набор данных можно скачать независимо от выбора.' : 'В этом разделе нет наблюдений.';
          }
          function selectPoint(id) {
            if (id && !activeRows().some(row => row.observation_id === id)) return;
            selectedPoints.set(active, id);
            pointFilter.value = id;
            page = 0; renderMap(); renderTable();
          }
          function activate(key) {
            active = key;
            page = 0;
            for (const [name, method] of Object.entries(methods)) {
              element(method.panel).classList.toggle('hidden', method.panel !== methods[key].panel);
              buttons[name].setAttribute('aria-pressed', String(name === key));
            }
            element('preliminaryDataTitle').textContent = methods[key].title;
            pointFilter.innerHTML = '<option value="">Все точки наблюдения</option>' + activeRows().map(row => `<option value="${escape(row.observation_id)}">${escape(row.observation_id)} · X ${number(row.x_m)}, Y ${number(row.y_m)} м</option>`).join('');
            pointFilter.value = selectedPoint();
            pointFilter.disabled = !activeRows().length;
            renderMap();
            renderTable();
          }
          pointFilter.addEventListener('change', () => selectPoint(pointFilter.value));
          for (const id of ['outcropMap', 'terrainSurveyMap', 'geophysicalMap']) {
            const map = element(id);
            map.addEventListener('click', event => {
              const dot = event.target.closest('[data-observation]');
              if (dot) selectPoint(dot.dataset.observation);
            });
            map.addEventListener('keydown', event => {
              if (!['Enter', ' '].includes(event.key)) return;
              const dot = event.target.closest('[data-observation]');
              if (dot) { event.preventDefault(); selectPoint(dot.dataset.observation); pointFilter.focus(); }
            });
          }
          element('downloadPreliminaryGeoJson').addEventListener('click', () => {
            const name = activeTable();
            const geojson = plan ? surveyGeoJson(name, activeRows()) : observations.geojson?.[name] ?? surveyGeoJson(name, activeRows());
            download(JSON.stringify(geojson, null, 2), `${name}.geojson`, 'application/geo+json');
          });
          element('downloadPreliminaryCsv').addEventListener('click', () => {
            const name = activeTable();
            downloadCsv(tableFields[name], activeRows(), `${name}.csv`);
          });
          element('preliminaryPrevious').addEventListener('click', () => { page--; renderTable(); });
          element('preliminaryNext').addEventListener('click', () => { page++; renderTable(); });
          activate(keys[0]);
          element('preliminaryEmpty').classList.add('hidden');
          element('preliminaryContent').classList.remove('hidden');
          buttons[keys[0]].focus();
        });
      }
      initPreliminary();
'''
