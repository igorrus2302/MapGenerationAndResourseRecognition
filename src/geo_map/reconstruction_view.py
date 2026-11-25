"""Independent visualization of the estimated geological grid and mineral zones."""

RECONSTRUCTION_STYLES = r'''
    .reconstruction-panel { margin-bottom:18px; }
    .reconstruction-controls { display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin:12px 0; }
    .reconstruction-controls label { flex:1 1 135px; min-width:0; max-width:420px; margin:0; }
    .reconstruction-controls select, .reconstruction-controls input { display:block; width:100%; margin-top:5px; }
    .reconstruction-actions { display:flex; flex-wrap:wrap; gap:8px; align-items:stretch; }
    .reconstruction-actions button { width:auto; }
    .reconstruction-svg { display:block; width:100%; height:clamp(300px, 70vh, 820px); background:#faf9f4; border:1px solid var(--line); cursor:grab; touch-action:none; user-select:none; }
    .reconstruction-svg [data-voxel]:hover { stroke:var(--ink); stroke-width:1.5; }
    .reconstruction-svg [data-selected="true"] { stroke:var(--highlight); stroke-width:1.8; }
    .reconstruction-legend { display:flex; gap:8px 14px; flex-wrap:wrap; margin:12px 0 0; font-size:12px; color:var(--muted); }
    .reconstruction-legend span { display:inline-flex; align-items:center; gap:5px; }
    .reconstruction-legend i { width:13px; height:13px; display:inline-block; border:1px solid var(--line); }
    .deposit-count-panel { margin-bottom:18px; }
    .deposit-count-panel td { vertical-align:middle; }
    .deposit-count-panel .deposit-count { font-size:18px; font-weight:650; color:var(--ink); }
    .deposit-count-panel .deposit-mineral { display:inline-flex; align-items:center; gap:8px; }
    .deposit-count-panel .deposit-mineral i { width:12px; height:12px; display:inline-block; flex-shrink:0; }
    .deposit-count-panel button { width:auto; padding:5px 9px; }
    .zone-card { border-top:1px solid var(--line); border-left:3px solid var(--zone-color); padding:15px 17px; margin-bottom:12px; background:var(--paper); overflow-wrap:anywhere; }
    .zone-card h3 { margin-bottom:5px; }
    .zone-card p { margin:8px 0; font-size:13px; line-height:1.6; }
    .zone-card button { width:auto; }
    .zone-tag { display:inline-block; padding:3px 7px; background:var(--surface-muted); color:var(--ink); font-size:11px; margin:2px 4px 2px 0; }
'''

RECONSTRUCTION_HTML = r'''
      <div class="expedition-heading">
        <div><h2>Восстановленная геологическая модель</h2></div>
        <div class="reconstruction-actions">
          <button id="downloadReconstructedMap" class="primary-button hidden">Скачать карту · JSON</button>
          <button id="downloadRecognition">Скачать результаты · JSON</button>
        </div>
      </div>
      <div id="reconstructionMissing" class="empty-card"><p>Объёмная модель ещё не построена.</p></div>
      <div id="reconstructedModel" class="hidden">
        <div class="panel-card reconstruction-panel">
          <div class="reconstruction-controls">
            <label>Ископаемое<select id="reconstructionMineral"><option value="">Все ископаемые</option></select></label>
            <div class="reconstruction-actions">
              <button id="reconstructionRotateLeft" type="button">↺ Повернуть</button>
              <button id="reconstructionRotateRight" type="button">Повернуть ↻</button>
              <button id="reconstructionResetView" type="button">Сбросить ракурс</button>
            </div>
          </div>
          <svg id="reconstructionSvg" class="reconstruction-svg" viewBox="0 0 760 490" role="img" aria-label="Рудные зоны. Перетаскивайте мышью для вращения, колесом меняйте масштаб."></svg>
          <div id="reconstructionLegend" class="reconstruction-legend"></div>
        </div>
      </div>
'''

MINERALS_PANEL = r'''
  <section id="mineralsPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-minerals">
    <div id="mineralsEmpty" class="empty-card"><h2>Найденные ископаемые</h2><p>Новая карта ещё не построена. Выполните распознавание по наблюдениям.</p></div>
    <div id="mineralsContent" class="hidden">
      <div class="expedition-heading"><div><h2>Найденные ископаемые</h2></div>
      </div>
      <div id="mineralResultsMetrics" class="metric-grid"></div>
      <div class="panel-card deposit-count-panel">
        <h3>Оценка объёма и массы залежей</h3>
        <div class="table-scroll">
          <table class="observation-table">
            <thead><tr><th>Полезное ископаемое</th><th>Зоны, шт.</th><th>Объём, м³</th><th>Масса породы, т</th><th>Среднее содержание</th><th>Масса компонента</th><th>Рудные зоны</th></tr></thead>
            <tbody id="mineralDepositEstimates"></tbody>
          </table>
        </div>
      </div>
      <div class="panel-card">
        <div class="profile-heading"><h3>Выделенные рудные зоны</h3><select id="mineralResultsFilter" aria-label="Фильтр ископаемых"><option value="">Все ископаемые</option></select></div>
        <div id="mineralZoneList" style="margin-top:14px"></div>
      </div>
      <div class="panel-card" style="margin-top:18px">
        <h3>Перспективные участки без прямого подтверждения</h3>
        <p class="muted">Почвенные и геофизические аномалии не считаются найденными залежами без положительных анализов керна или канавных проб.</p>
        <div id="mineralAnomaliesSummary" class="selection-detail"></div>
        <div class="table-scroll"><table class="observation-table"><thead><tr><th>Проба</th><th>Компонент</th><th>X / Y, м</th><th>Результат / порог</th></tr></thead><tbody id="mineralAnomalyList"></tbody></table></div>
      </div>
    </div>
  </section>
'''

RECONSTRUCTION_SCRIPT = r'''
      function renderReconstruction(result) {
        const model = result?.reconstructed_map;
        if (!model) return;
        element('reconstructedModel').classList.remove('hidden');
        element('reconstructionMissing').classList.add('hidden');
        element('downloadReconstructedMap').classList.remove('hidden');
        element('mineralsEmpty').classList.add('hidden');
        element('mineralsContent').classList.remove('hidden');
        const d = model.dimensions, s = model.summary, zones = model.mineral_zones;
        const nx = d.width_cells, ny = d.height_cells, nz = d.depth_cells, plane = nx*ny;
        const dx = d.cell_size_x_m, dy = d.cell_size_y_m, dz = d.depth_step_m;
        const numberFormat = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2});
        const fmt = value => numberFormat.format(Number(value));
        const quantity = value => value == null || !Number.isFinite(value) ? 'н/д' : fmt(value);
        const componentMass = value => value == null || !Number.isFinite(value) ? 'н/д' :
          value === 0 || value >= 1 ? fmt(value)+' т' :
          value >= .001 ? fmt(value*1000)+' кг' : Number(value*1e6).toLocaleString('ru-RU',{maximumFractionDigits:3})+' г';
        const gradeText = resources => resources?.average_grade == null ? 'н/д' :
          Number(resources.average_grade).toLocaleString('ru-RU',{maximumFractionDigits:6})+' '+escape(resources.grade_unit);
        const densitySource = {measured_core:'измерения плотности керна',rock_catalog:'справочник пород',unavailable:'нет данных о плотности'};
        const resourceDetails = resources => {
          if(!resources)return '<p class="muted">Для оценки массы пересчитайте распознавание.</p>';
          return '<p><strong>Оценочный объём:</strong> '+quantity(resources.volume_m3)+' м³'+
            ' · <strong>Масса минерализованной породы:</strong> '+quantity(resources.ore_mass_t)+(resources.ore_mass_t==null?'':' т')+
            '<br><strong>Среднее содержание:</strong> '+gradeText(resources)+' · <strong>Масса компонента:</strong> '+componentMass(resources.component_mass_t)+
            '<br><strong>Принятая плотность:</strong> '+quantity(resources.density_t_m3)+(resources.density_t_m3==null?'':' т/м³')+
            ' ('+escape(densitySource[resources.density_source]||'нет данных')+')'+
            '<br><strong>Объём ячеек с пересечёнными пробами:</strong> '+quantity(resources.observed_cells_volume_m3)+' м³ · <strong>Объём интерполированных ячеек:</strong> '+quantity(resources.interpolated_cells_volume_m3)+' м³</p>';
        };
        const coords = i => [i%nx, Math.floor(i/nx)%ny, Math.floor(i/plane)];
        const ore = new Map();
        for (const zone of zones) for (const [i,status] of zone.cells) {
          if (!ore.has(i)) ore.set(i, []);
          ore.get(i).push({zone,status});
        }
        const minerals = [...new Map(zones.map(z => [z.mineral_id,z])).values()];
        // Older exports without the summary can derive the same counts from their zones.
        const deposits = model.mineral_deposit_estimates ?? minerals.map(mineral => {
          const group = zones.filter(zone => zone.mineral_id === mineral.mineral_id);
          const multiSite = group.filter(zone => zone.sites.length >= 2).length;
          return {mineral_id:mineral.mineral_id, name:mineral.name, analyte:mineral.analyte, color:mineral.color,
                  estimated_deposit_count:group.length, multi_site_zone_count:multiSite,
                  single_site_zone_count:group.length-multiSite, zone_ids:group.map(zone => zone.zone_id),
                  resources:{volume_m3:group.reduce((sum,zone)=>sum+zone.cells.length*dx*dy*dz,0)}};
        });
        const mineralOptions = '<option value="">Все ископаемые</option>' + minerals.map(z => '<option value="'+escape(z.mineral_id)+'">'+escape(z.name)+'</option>').join('');
        const filter = element('reconstructionMineral'), resultsFilter = element('mineralResultsFilter');
        filter.innerHTML = mineralOptions;
        resultsFilter.innerHTML = '<option value="">Все ископаемые</option>' + deposits.map(z => '<option value="'+escape(z.mineral_id)+'">'+escape(z.name)+' · залежей: '+z.estimated_deposit_count+'</option>').join('');
        element('mineralDepositEstimates').innerHTML = deposits.length ? deposits.map(z =>
          '<tr data-mineral-estimate="'+escape(z.mineral_id)+'"><td><span class="deposit-mineral"><i style="background:'+escape(z.color)+'"></i>'+escape(z.name)+' · '+escape(z.analyte)+'</span></td>'+
          '<td class="deposit-count">'+fmt(z.estimated_deposit_count)+'</td><td data-resource-volume>'+quantity(z.resources?.volume_m3)+'</td>'+
          '<td data-resource-ore-mass>'+quantity(z.resources?.ore_mass_t)+'</td><td>'+gradeText(z.resources)+'</td><td data-resource-component-mass>'+componentMass(z.resources?.component_mass_t)+'</td>'+
          '<td><button type="button" data-deposit-mineral="'+escape(z.mineral_id)+'">Показать зоны</button></td></tr>'
        ).join('') : '<tr><td colspan="7">Залежи по имеющимся наблюдениям не выделены.</td></tr>';
        const cards = values => values.map(([v,l]) => '<div class="metric-card"><strong>'+escape(v)+'</strong><span>'+escape(l)+'</span></div>').join('');
        element('mineralResultsMetrics').innerHTML = cards([[s.mineral_types,'видов ископаемых'],[s.estimated_deposit_count ?? s.mineral_zone_count,'предполагаемых залежей'],[s.observed_mineral_cells,'ячеек с положительными пробами'],[s.interpolated_mineral_cells,'оценённых рудных ячеек']]);
        const svg = element('reconstructionSvg');
        const supportLabels = {'-1':'Выше оценённой поверхности','0':'Нет данных','1':'Интерполировано','2':'Пересекает наблюдение'};
        let selectedVoxel = null;
        function matching(i) {
          return (ore.get(i)||[]).filter(({zone}) => (!filter.value || zone.mineral_id===filter.value));
        }
        const legend = (color,label) => '<span><i style="background:'+escape(color)+'"></i>'+escape(label)+'</span>';
        function cellTitle(i) {
          const [x,y,z] = coords(i), r = model.rock_catalog[model.lithology[i]-1];
          const info = ['X: '+fmt(x*dx)+'–'+fmt((x+1)*dx)+' м · Y: '+fmt(y*dy)+'–'+fmt((y+1)*dy)+' м',
            'Высота: '+fmt(d.top_elevation_m-(z+1)*dz)+'…'+fmt(d.top_elevation_m-z*dz)+' м',
            'Порода: '+(r?.name || 'не определена'), 'Основание: '+supportLabels[model.lithology_support[i]]];
          const finds = (ore.get(i)||[]).map(({zone,status}) => zone.analyte+' · '+zone.zone_id+' · '+(status===2?'положительная проба пересекает ячейку':'интерполированное продолжение'));
          return escape(info.concat(finds).join('\n'));
        }
        // Match the true-map controls, but render only cells assigned to mineral zones.
        const defaultAngle = -Math.PI / 4;
        let angle = defaultAngle, zoom = 1, drag = null, suppressClick = false;
        const width = d.width_m, height = d.height_m, depth = nz * dz;
        function volumeProjection() {
          const sin = Math.sin(angle), cos = Math.cos(angle);
          const tilt = 0.46, vertical = Math.sqrt(1 - tilt * tilt);
          const raw = (x,y,z) => {
            const cx=x-width/2, cy=y-height/2;
            const rx=cx*cos-cy*sin, ry=cx*sin+cy*cos;
            return {x:rx,y:ry*tilt+z*vertical,depth:ry*vertical-z*tilt};
          };
          const corners=[];
          for(const x of [0,width]) for(const y of [0,height]) for(const z of [0,depth]) corners.push(raw(x,y,z));
          const minX=Math.min(...corners.map(p=>p.x)), maxX=Math.max(...corners.map(p=>p.x));
          const minY=Math.min(...corners.map(p=>p.y)), maxY=Math.max(...corners.map(p=>p.y));
          const scale=Math.min(690/(maxX-minX),420/(maxY-minY))*zoom;
          const point=(x,y,z)=>{const p=raw(x,y,z);return {x:380+(p.x-(minX+maxX)/2)*scale,y:245+(p.y-(minY+maxY)/2)*scale,depth:p.depth};};
          return {point,sin,cos};
        }
        function drawVolume() {
          const {point,sin,cos}=volumeProjection();
          // A wireframe marks the surveyed extent without rendering any host-rock voxels.
          const outline=[];
          function edge(a,b) {
            const p=point(...a), q=point(...b);
            outline.push('<line x1="'+p.x+'" y1="'+p.y+'" x2="'+q.x+'" y2="'+q.y+'"/>');
          }
          for(const z of [0,depth]) {
            edge([0,0,z],[width,0,z]);edge([width,0,z],[width,height,z]);
            edge([width,height,z],[0,height,z]);edge([0,height,z],[0,0,z]);
          }
          for(const x of [0,width]) for(const y of [0,height]) edge([x,y,0],[x,y,depth]);
          let out='<g data-model-outline="true" fill="none" stroke="#b3b2a4" stroke-width=".8" pointer-events="none">'+outline.join('')+'</g>';
          const faces=[];
          function addFace(vertices,fill,opacity,i,title) {
            const points=vertices.map(p=>point(...p));
            faces.push({points,fill,opacity,i,title,depth:points.reduce((sum,p)=>sum+p.depth,0)/points.length});
          }
          for(const i of ore.keys()) {
            const match=matching(i)[0];
            if(!match)continue;
            const [ix,iy,iz]=coords(i), x=ix*dx,y=iy*dy,z=iz*dz, X=x+dx,Y=y+dy,Z=z+dz;
            const {zone,status}=match, c=escape(zone.color), op=status===2?.98:.65;
            const nearX=sin>=0?X:x, nearY=cos>=0?Y:y, title=cellTitle(i);
            addFace([[x,y,z],[X,y,z],[X,Y,z],[x,Y,z]],c,op,i,title);
            addFace([[x,nearY,z],[X,nearY,z],[X,nearY,Z],[x,nearY,Z]],c,op*.8,i,title);
            addFace([[nearX,y,z],[nearX,Y,z],[nearX,Y,Z],[nearX,y,Z]],c,op*.65,i,title);
          }
          faces.sort((a,b)=>a.depth-b.depth);
          out+=faces.map(({points,fill,opacity,i,title})=>'<polygon points="'+points.map(p=>p.x+','+p.y).join(' ')+'" fill="'+fill+'" fill-opacity="'+opacity+'" stroke="#64748b" stroke-width=".6" data-voxel="'+i+'"'+(i===selectedVoxel?' data-selected="true"':'')+'><title>'+title+'</title></polygon>').join('');
          if(!faces.length)out+='<text x="380" y="245" text-anchor="middle" fill="#64748b">Нет рудных зон для отображения</text>';
          svg.innerHTML=out;
        }
        function drawLegend() {
          element('reconstructionLegend').innerHTML=minerals.filter(z=>!filter.value||filter.value===z.mineral_id).map(z=>legend(z.color,z.analyte)).join('');
        }
        filter.addEventListener('change',()=>{selectedVoxel=null;drawVolume();drawLegend();});
        element('reconstructionRotateLeft').addEventListener('click',()=>{angle-=Math.PI/8;drawVolume();});
        element('reconstructionRotateRight').addEventListener('click',()=>{angle+=Math.PI/8;drawVolume();});
        element('reconstructionResetView').addEventListener('click',()=>{angle=defaultAngle;zoom=1;drawVolume();});
        svg.addEventListener('pointerdown',event=>{
          if(event.button!==0||drag)return;
          drag={id:event.pointerId,startX:event.clientX,lastX:event.clientX,moved:false};
          suppressClick=false;
        });
        svg.addEventListener('pointermove',event=>{
          if(!drag||drag.id!==event.pointerId)return;
          if(!drag.moved&&Math.abs(event.clientX-drag.startX)<3)return;
          if(!drag.moved){drag.moved=true;svg.setPointerCapture?.(event.pointerId);svg.style.cursor='grabbing';}
          angle+=(event.clientX-drag.lastX)*.012;
          drag.lastX=event.clientX;drawVolume();
        });
        function finishDrag(event) {
          if(!drag||drag.id!==event.pointerId)return;
          suppressClick=drag.moved;drag=null;svg.style.cursor='grab';
          if(svg.hasPointerCapture?.(event.pointerId))svg.releasePointerCapture(event.pointerId);
        }
        svg.addEventListener('pointerup',finishDrag);
        svg.addEventListener('pointercancel',finishDrag);
        svg.addEventListener('lostpointercapture',finishDrag);
        svg.addEventListener('pointerleave',event=>{if(drag&&!drag.moved)finishDrag(event);});
        svg.addEventListener('wheel',event=>{
          event.preventDefault();zoom=Math.max(.55,Math.min(1.8,zoom*(event.deltaY>0?.92:1.08)));drawVolume();
        },{passive:false});
        svg.addEventListener('click',event=>{
          if(suppressClick){suppressClick=false;return;}
          const v=event.target.closest('[data-voxel]');
          if(v){selectedVoxel=Number(v.dataset.voxel);drawVolume();}
        });
        const labels={host_rock:'Вмещающая порода',observed_fault:'Разлом',steep_fault:'Крутой разлом',observed_contact:'Контакт пород',intrusive_rock:'Интрузия',compatible_core_properties:'Плотность и пористость',adjacent_positive_samples:'Смежные положительные пробы',nearby_soil_anomaly:'Почвенная аномалия',terrain_bauxite_depression:'Рельеф',terrain_exposed_host:'Обнажение',geophysics_magnetic:'Магнитная аномалия',geophysics_gamma:'Гамма-аномалия',downhole_gamma_anomaly:'Гамма-каротаж',downhole_magnetic_anomaly:'Магнитный каротаж'};
        function drawResults(){
          const list=zones.filter(z=>!resultsFilter.value||z.mineral_id===resultsFilter.value);
          element('mineralZoneList').innerHTML=list.length?list.map(z=>{
            const b=z.bounds_m;
            return '<article class="zone-card" style="--zone-color:'+escape(z.color)+'"><h3>'+escape(z.name)+' · '+escape(z.analyte)+'</h3><div class="muted">'+escape(z.zone_id)+' · '+escape(z.sites.join(', '))+'</div><p><strong>Пиковое измеренное содержание:</strong> '+fmt(z.peak_measured_grade)+' '+escape(z.unit)+' (порог '+fmt(z.threshold)+')<br><strong>Пробы:</strong> '+z.sample_count+' · <strong>Ячейки:</strong> '+z.observed_cell_count+' по наблюдениям, '+z.interpolated_cell_count+' по интерполяции<br><strong>Границы сеточной зоны:</strong> X '+b.x.map(fmt).join('–')+' м, Y '+b.y.map(fmt).join('–')+' м, отметки '+b.elevation.map(fmt).join('…')+' м</p>'+resourceDetails(z.resources)+'<p><strong>Измеренные интервалы:</strong> '+(z.measured_intervals||[]).map(t=>escape(t.site_id)+' '+fmt(t.from_m)+'–'+fmt(t.to_m)+' м вдоль траектории').join(' · ')+'</p><p>'+z.signals.map(x=>'<span class="zone-tag">'+escape(labels[x]||x)+'</span>').join('')+'</p><button data-zone="'+escape(z.zone_id)+'">Показать на карте</button></article>';
          }).join(''):'<p class="muted">Нет выделенных зон для выбранного компонента.</p>';
        }
        resultsFilter.addEventListener('change',drawResults);
        element('mineralDepositEstimates').addEventListener('click',event=>{
          const button=event.target.closest('[data-deposit-mineral]');
          if(!button)return;
          resultsFilter.value=button.dataset.depositMineral;
          drawResults();
        });
        element('mineralZoneList').addEventListener('click',event=>{
          const button=event.target.closest('[data-zone]'); if(!button)return;
          const z=zones.find(z=>z.zone_id===button.dataset.zone); if(!z)return;
          filter.value=z.mineral_id;
          selectedVoxel=z.cells.find(c=>c[1]===2)?.[0]??z.cells[0][0];drawVolume();drawLegend();element('tab-recognized').click();
        });
        element('mineralAnomaliesSummary').textContent='Почвенных аномалий: '+model.soil_anomalies.length+' · геофизических аномалий: '+(result.geophysical_anomalies||[]).length+' · Интервалов магнитного каротажа с аномалиями: '+(result.summary?.downhole_magnetic_anomaly_count??0);
        element('mineralAnomalyList').innerHTML=model.soil_anomalies.length?model.soil_anomalies.map(t=>'<tr><td>'+escape(t.site_id)+'</td><td>'+escape(t.analyte)+'</td><td>'+t.center_xyz_m.slice(0,2).map(fmt).join(' / ')+'</td><td>'+fmt(t.peak_result)+' / '+fmt(t.threshold)+' '+escape(t.unit)+'</td></tr>').join(''):'<tr><td colspan="4">Нет почвенных аномалий</td></tr>';
        element('downloadReconstructedMap').addEventListener('click',()=>download(JSON.stringify(model,null,2),'reconstructed_map.json','application/json'));
        drawVolume();drawLegend();drawResults();
      }
'''
