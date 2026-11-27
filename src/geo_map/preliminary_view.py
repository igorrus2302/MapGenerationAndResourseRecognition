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

      // Interpolate measured values only. The true map is never used by the
      // cartographic renderer. Cache the raster while selecting survey points.
      const rasterCache = new WeakMap();
      function surveyRaster(rows, field, isElevation = false) {
        if (!rows.length) return '';
        const cached = rasterCache.get(rows);
        if (cached?.field === field && cached.length === rows.length) return cached.markup;
        const nx = Math.max(8, Math.round(54 * Math.min(1, dims.width_m / dims.height_m)));
        const ny = Math.max(8, Math.round(54 * Math.min(1, dims.height_m / dims.width_m)));
        const groups = new Map();
        let low = Infinity, high = -Infinity;
        for (const row of rows) {
          const value = row[field];
          if (!Number.isFinite(value) || !Number.isFinite(row.x_m) || !Number.isFinite(row.y_m)) continue;
          low = Math.min(low, value); high = Math.max(high, value);
          // Bound the interpolation cost for large imported surveys.
          const x = Math.max(0, Math.min(dims.width_m, row.x_m));
          const y = Math.max(0, Math.min(dims.height_m, row.y_m));
          const key = Math.min(nx - 1, Math.floor(x / dims.width_m * nx)) + nx * Math.min(ny - 1, Math.floor(y / dims.height_m * ny));
          const group = groups.get(key) ?? {x: 0, y: 0, value: 0, count: 0};
          group.x += x; group.y += y; group.value += value; group.count++;
          groups.set(key, group);
        }
        if (!groups.size) return '';
        const samples = [...groups.values()].map(g => ({x:g.x/g.count, y:g.y/g.count, value:g.value/g.count}));
        const dx = dims.width_m / nx, dy = dims.height_m / ny;
        const values = [];
        for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
          let weighted = 0, weight = 0;
          for (const sample of samples) {
            const d = ((x+.5)*dx-sample.x)**2 + ((y+.5)*dy-sample.y)**2;
            const w = 1 / Math.max(d, 0.01)**2;
            weighted += sample.value * w; weight += w;
          }
          values.push(weighted / weight);
        }
        const frame = mapFrame(dims), palette = ['#477581', '#79a785', '#c3c38a', '#eee0c3'];
        const color = fraction => isElevation
          ? palette[Math.min(palette.length - 1, Math.floor(fraction * palette.length))]
          : geophysicalColor(fraction);
        let markup = '<g data-survey-raster="true" pointer-events="none">';
        const origin = frame.point(0, 0), step = frame.point(dx, dy);
        const cellW = step.x - origin.x, cellH = origin.y - step.y;
        for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
          const value = values[y*nx+x];
          const fraction = high === low ? .5 : Math.max(0, Math.min(1, (value-low)/(high-low)));
          const position = frame.point(x*dx, (y+1)*dy);
          let fill = color(fraction);
          if (isElevation) {
            const x1=Math.min(nx-1,x+1), x0=Math.max(0,x-1), y1=Math.min(ny-1,y+1), y0=Math.max(0,y-1);
            const shade=Math.max(.68,Math.min(1.28,1.05+((values[y*nx+x1]-values[y*nx+x0])/dx+(values[y1*nx+x]-values[y0*nx+x])/dy)/4));
            fill=rgba(fill,1,shade);
          }
          markup += `<rect x="${position.x.toFixed(2)}" y="${position.y.toFixed(2)}" width="${(cellW+.02).toFixed(2)}" height="${(cellH+.02).toFixed(2)}" fill="${fill}"/>`;
        }
        markup += '</g>';
        for (let i=0;i<20;i++) markup += `<rect x="${245+i*8}" y="280" width="8" height="7" fill="${color(i/19)}"/>`;
        const unit = isElevation ? 'м' : field === 'magnetic_anomaly_nt' ? 'нТл' : 'имп/с';
        markup += `<text x="241" y="287" text-anchor="end" font-size="10" fill="#62675e">${number(low)}</text><text x="409" y="287" font-size="10" fill="#62675e">${number(high)} ${unit}</text>`;
        rasterCache.set(rows, {field, length: rows.length, markup});
        return markup;
      }

      function drawPreliminaryMap(method, rows, settings, selectedId, terrainRows) {
        const {point, markup} = mapFrame(dims);
        const radius = Math.max(1.25, Math.min(4.25, 85 / Math.sqrt(rows.length || 1)));
        const selectedRow = rows.find(row => row.observation_id === selectedId);
        const points = selectedRow ? [...rows.filter(row => row !== selectedRow), selectedRow] : rows;
        const attributes = (row, x, y, size, border = 'none') => {
          const selected = row.observation_id === selectedId;
          return `class="hole-dot" role="button" tabindex="0" aria-label="${escape(row.observation_id)}" aria-pressed="${selected}" data-observation="${escape(row.observation_id)}" cx="${x}" cy="${y}" r="${selected ? Math.max(6, size + 2) : size}" stroke="${selected ? '#a35a35' : border}" stroke-width="${selected ? 3 : 1}"`;
        };
        if (method === 'outcrops') {
          element('outcropMap').innerHTML = markup + surveyRaster(terrainRows, 'surface_elevation_m', true) + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const color = rockById[row.observed_rock_id]?.color || '#355d48';
            return `<circle ${attributes(row, x, y, 4.5, '#30382f')} fill="${escape(color)}"><title>${escape(row.observation_id)} · ${escape(row.observed_rock_name)} · ${number(row.surface_elevation_m)} м</title></circle>`;
          }).join('');
          element('outcropCaption').textContent = `${number(rows.length)} обнажений на ${number(settings.points?.length ?? settings.point_count ?? rows.length)} обследованных точках. Цвет точек соответствует наблюдённой породе. Фон — интерполяция измеренных высот (если есть).`;
        } else if (method === 'terrain_survey') {
          const counts = new Map();
          element('terrainSurveyMap').innerHTML = markup + surveyRaster(rows, 'surface_elevation_m', true) + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const type = terrainTypes[row.terrain_type] || terrainTypes.undetermined;
            counts.set(type.label, (counts.get(type.label) || 0) + 1);
            return `<circle ${attributes(row, x, y, radius)} fill="${type.color}"><title>${escape(row.observation_id)} · ${type.label} · ${number(row.surface_elevation_m)} м</title></circle>`;
          }).join('');
          element('terrainSurveyCaption').textContent = `Фон — интерполяция высот; точки — типы рельефа. ${number(rows.length)} точек · порог уклона ${settings.slope_threshold_deg == null?'не задан':number(settings.slope_threshold_deg)+'°'} · порог относительной высоты ${settings.local_relief_threshold_m == null?'не задан':number(settings.local_relief_threshold_m)+' м'}`;
          element('terrainSurveyLegend').innerHTML = Object.values(terrainTypes).filter(type => counts.has(type.label))
            .map(type => `<span style="color:${type.color}">● ${type.label} · ${number(counts.get(type.label))}</span>`).join(' &nbsp; ');
        } else {
          const {field, label, unit} = geophysicalChannels[surveyChannels[method]];
          element('geophysicalHeading').textContent = label;
          const values = rows.map(row => row[field]);
          const minimum = values.reduce((a,b)=>Math.min(a,b), Infinity), maximum = values.reduce((a,b)=>Math.max(a,b), -Infinity);
          element('geophysicalMap').innerHTML = markup + surveyRaster(rows, field) + points.map(row => {
            const {x, y} = point(row.x_m, row.y_m);
            const scaled = minimum === maximum ? .5 : (row[field] - minimum) / (maximum - minimum);
            return `<circle ${attributes(row, x, y, radius, '#ffffff')} fill="${geophysicalColor(scaled)}" stroke-opacity=".85"><title>${escape(row.observation_id)} · ${label} ${number(row[field])} ${unit}</title></circle>`;
          }).join('');
          element('geophysicalCaption').textContent = rows.length
            ? `Интерполяция измерений · ${number(rows.length)} точек · от ${number(minimum)} ${unit} (синий) до ${number(maximum)} ${unit} (оранжевый)`
            : 'Для этого канала пока нет измерений.';
        }
      }

      function initPreliminary() {
        const plan = PRELIMINARY_PLAN;
        const settings = plan?.methods ?? observations?.plan?.methods ?? {};
        const tableFields = observations?.table_fields ?? plan?.table_fields ?? {};
        const definitions = {
          magnetic_observations: {label: 'Магнитное поле', panel: 'geophysicalOverview', table: 'magnetic_observations',
            title: 'Магнитные наблюдения', archiveSetting: 'geophysical_survey'},
          gamma_observations: {label: 'Гамма-фон', panel: 'geophysicalOverview', table: 'gamma_observations',
            title: 'Радиометрические наблюдения', archiveSetting: 'geophysical_survey'},
          terrain_survey: {label: 'Рельеф', panel: 'terrainSurveyOverview', table: 'terrain_observations', title: 'Точки съёмки рельефа'},
          outcrops: {label: 'Обнажения', panel: 'outcropOverview', table: 'outcrop_observations', title: 'Наблюдения обнажений'}
        };
        const enabled = Object.fromEntries(Object.entries(definitions).filter(([key, {table, archiveSetting}]) =>
          (plan ? settings[key] : settings[archiveSetting ?? key]?.enabled) && tableFields[table]));
        const methods = observations
          ? Object.fromEntries(Object.entries(definitions).filter(([, {table}])=>tableFields[table]))
          : enabled;
        const keys = Object.keys(methods);
        const start = element('collectPreliminary');
        const manual = element('openManualPreliminary');
        const status = element('preliminaryStatus');
        if(!observations)manual.classList.add('hidden');
        if(!Object.keys(enabled).length && !OBSERVATION_DATA){
          if (!COLLECT_ENDPOINT) start.classList.add('hidden');
          else start.textContent='Завершить предварительный этап без съёмки';
          status.textContent='Автоматическая съёмка отключена. Можно загрузить свои наблюдения вручную.';
        }
        if(!keys.length)return;
        function openSections(collect = false) {
          if (start.disabled) return;
          start.disabled = true;
          manual.disabled = true;
          let results;
          try {
            // Opening the manual workspace never samples the true map.
            // Historical exports contain measurements from an earlier run.
            if (collect && !OBSERVATION_DATA) {
              const generated = collectSurvey(plan);
              if (observations) {
                for (const [table, rows] of Object.entries(generated)) {
                  observations.tables[table] = rows;
                  observations.geojson[table] = surveyGeoJson(table, rows);
                }
                Object.assign(observations.summary, {
                  magnetic_observation_count: (generated.magnetic_observations || []).length,
                  gamma_observation_count: (generated.gamma_observations || []).length,
                  terrain_observation_count: (generated.terrain_observations || []).length,
                  outcrop_count: (generated.outcrop_observations || []).length,
                  geophysical_observation_count: new Set([...(generated.magnetic_observations || []), ...(generated.gamma_observations || [])].map(row=>row.station_id)).size
                });
              }
              results = observations?.tables ?? generated;
            } else {
              results = observations?.tables ?? {};
            }
          } catch {
            start.disabled = false;
            manual.disabled = false;
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
            drawPreliminaryMap(active, activeRows(), settings[active] ?? settings[methods[active].archiveSetting] ?? {}, selectedPoint(), results.terrain_observations || []);
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
          let updateImportHint=()=>{};
          function activate(key) {
            active = key;
            updateImportHint();
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
            const geojson = observations?.geojson?.[name] ?? surveyGeoJson(name, activeRows());
            download(JSON.stringify(geojson, null, 2), `${name}.geojson`, 'application/geo+json');
          });
          element('downloadPreliminaryCsv').addEventListener('click', () => {
            const name = activeTable();
            downloadCsv(tableFields[name], activeRows(), `${name}.csv`);
          });
          element('preliminaryPrevious').addEventListener('click', () => { page--; renderTable(); });
          element('preliminaryNext').addEventListener('click', () => { page++; renderTable(); });
          activate(keys[0]);
          updateImportHint=setupImportControls('preliminary',activeTable,()=>[activeTable()],()=>'',updateExpeditionStart);
          refreshPreliminary=()=>activate(active);
          element('preliminaryEmpty').classList.add('hidden');
          element('preliminaryContent').classList.remove('hidden');
          buttons[keys[0]].focus();
        }
        if (OBSERVATION_DATA && !PRELIMINARY_COLLECTED) {
          start.textContent = 'Открыть сохранённые наблюдения';
          status.textContent = 'Это сохранённый результат экспедиции. Откройте наблюдения для просмотра карт и измерений.';
        }
        start.addEventListener('click', async () => {
          if (!COLLECT_ENDPOINT) {
            openSections(true);
            return;
          }
          if (start.disabled) return;
          start.disabled = manual.disabled = true;
          status.textContent = 'Выполняется только предварительная съёмка…';
          try {
            const response = await fetch(COLLECT_ENDPOINT, {method:'POST'});
            if (!response.ok) throw new Error('Ошибка сбора наблюдений');
            location.reload();
          } catch (error) {
            start.disabled = manual.disabled = false;
            status.textContent = 'Не удалось собрать наблюдения. Проверьте сообщения в терминале и повторите попытку.';
          }
        });
        manual.addEventListener('click', () => openSections(false));
        if (PRELIMINARY_COLLECTED) openSections(false);
      }
      initPreliminary();
'''
