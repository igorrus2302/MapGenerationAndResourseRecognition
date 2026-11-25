"""Independent visualization of the estimated geological grid and mineral zones."""

RECONSTRUCTION_STYLES = r'''
    .reconstruction-grid { display:grid; grid-template-columns:minmax(300px, 2fr) minmax(240px,1fr); gap:16px; align-items:start; margin-bottom:18px; }
    .reconstruction-controls { display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin:12px 0; }
    .reconstruction-controls label { flex:1 1 135px; margin:0; }
    .reconstruction-controls select, .reconstruction-controls input { display:block; width:100%; margin-top:5px; }
    .reconstruction-svg { display:block; width:100%; height:clamp(300px, 56vh, 600px); background:#f8fafc; border:1px solid var(--line); border-radius:8px; }
    .reconstruction-svg [data-voxel] { cursor:crosshair; }
    .reconstruction-svg [data-voxel]:hover { stroke:#1e293b; stroke-width:1.5; }
    .reconstruction-legend { display:flex; gap:8px 14px; flex-wrap:wrap; margin:12px 0; font-size:12px; }
    .reconstruction-legend span { display:inline-flex; align-items:center; gap:5px; }
    .reconstruction-legend i { width:13px; height:13px; display:inline-block; border:1px solid #c4cdd6; border-radius:2px; }
    .deposit-count-panel { margin-bottom:18px; }
    .deposit-count-panel td { vertical-align:middle; }
    .deposit-count-panel .deposit-count { font-size:20px; font-weight:700; color:var(--text); }
    .deposit-count-panel .deposit-mineral { display:inline-flex; align-items:center; gap:8px; }
    .deposit-count-panel .deposit-mineral i { width:12px; height:12px; border-radius:3px; display:inline-block; flex-shrink:0; }
    .deposit-count-panel button { width:auto; padding:5px 9px; }
    .zone-card { border:1px solid var(--line); border-left:5px solid var(--zone-color); padding:15px 17px; border-radius:9px; margin-bottom:12px; }
    .zone-card h3 { margin-bottom:5px; }
    .zone-card p { margin:8px 0; font-size:13px; line-height:1.5; }
    .zone-card button { width:auto; }
    .zone-tag { display:inline-block; padding:3px 8px; background:#edf5f8; color:#345b70; border-radius:10px; font-size:11px; margin:2px 4px 2px 0; }
    @media(max-width:1050px) { .reconstruction-grid { grid-template-columns:1fr; } }
'''

RECONSTRUCTION_HTML = r'''
      <div id="reconstructedModel" class="hidden">
        <div class="expedition-heading">
          <div><h2>Восстановленная геологическая модель</h2><p>Построена только по данным съёмки, скважин, траншей и проб. Истинная карта не использовалась.</p></div>
          <button id="downloadReconstructedMap" class="primary-button">Скачать карту · JSON</button>
        </div>
        <div id="reconstructionMetrics" class="metric-grid"></div>
        <div class="reconstruction-grid">
          <div class="panel-card">
            <h3>Пространственная карта</h3>
            <div class="reconstruction-controls">
              <label>Вид<select id="reconstructionMode">
                <option value="xy">Горизонтальный разрез X–Y</option><option value="xz">Вертикальный разрез X–Z</option><option value="yz">Вертикальный разрез Y–Z</option>
                <option value="3d">Объёмная геологическая модель</option><option value="terrain">Восстановленный рельеф</option>
                <option value="magnetic">Магнитное поле</option><option value="gamma">Гамма-фон</option>
              </select></label>
              <label id="reconstructionSliceLabel"><span id="reconstructionSliceCaption">Отметка разреза</span><input id="reconstructionSlice" type="range" min="0" max="0" value="0" step="1"></label>
              <label>Слой<select id="reconstructionLayer"><option value="all">Породы и рудные зоны</option><option value="rocks">Только породы</option><option value="ore">Только рудные зоны</option><option value="support">Обеспеченность данными</option></select></label>
              <label>Ископаемое<select id="reconstructionMineral"><option value="">Все ископаемые</option></select></label>
            </div>
            <svg id="reconstructionSvg" class="reconstruction-svg" viewBox="0 0 760 490" role="img" aria-label="Восстановленная пространственная модель"></svg>
            <div id="reconstructionLegend" class="reconstruction-legend"></div>
          </div>
          <div class="panel-card">
            <h3>Информация о ячейке</h3>
            <p id="reconstructionCellInfo" class="selection-detail">Выберите ячейку на карте для просмотра породы, глубины и обнаруженных компонентов.</p>
            <h3 style="margin-top:24px">Как читать карту</h3>
            <p class="muted">Насыщенный цвет и контур — ячейка пересекает измеренную траекторию или точку. Бледный цвет — интерполяция. Серый — недостаточно данных. Белый — выше оценённой поверхности.</p>
            <p class="muted">Рудная зона показывает положение положительных проб и продолжение между измерениями. Объём и масса на вкладке 05 рассчитаны при допущении полного заполнения выделенных ячеек; это ориентировочная оценка, а не доказанные запасы.</p>
            <p id="reconstructionExtent" class="selection-detail"></p>
            <button id="openMineralResults" type="button">Найденные ископаемые →</button>
          </div>
        </div>
      </div>
'''

MINERALS_PANEL = r'''
  <section id="mineralsPanel" class="workspace-page hidden" role="tabpanel" aria-labelledby="tab-minerals">
    <div id="mineralsEmpty" class="empty-card"><h2>Найденные ископаемые</h2><p>Новая карта ещё не построена. Выполните распознавание по наблюдениям.</p></div>
    <div id="mineralsContent" class="hidden">
      <div class="expedition-heading"><div><h2>Найденные ископаемые</h2><p id="mineralResultsSummary"></p></div>
        <button id="backToReconstruction">К восстановленной карте</button>
      </div>
      <div id="mineralResultsMetrics" class="metric-grid"></div>
      <div class="panel-card deposit-count-panel">
        <h3>Оценка объёма и массы залежей</h3>
        <p class="muted">Суммарные показатели по каждому виду ископаемого. Объём равен объёму выделенных ячеек модели, масса минерализованной породы рассчитывается по плотности, а масса компонента — по среднему содержанию. Расчёт предполагает полное заполнение выделенных ячеек и не является оценкой доказанных запасов.</p>
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
        element('mineralsEmpty').classList.add('hidden');
        element('mineralsContent').classList.remove('hidden');
        const d = model.dimensions, s = model.summary, zones = model.mineral_zones;
        const nx = d.width_cells, ny = d.height_cells, nz = d.depth_cells, plane = nx*ny;
        const dx = d.cell_size_x_m, dy = d.cell_size_y_m, dz = d.depth_step_m;
        const fmt = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 2});
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
        const index = (x,y,z) => z*plane+y*nx+x;
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
        element('reconstructionMetrics').innerHTML = cards([[fmt(s.cell_count),'ячеек 3D-сетки'],[fmt(s.observed_lithology_cells),'пересекают наблюдения'],[fmt(s.interpolated_lithology_cells),'пород интерполировано, ячеек'],[fmt(s.unknown_cells),'без данных о породах']]);
        element('mineralResultsMetrics').innerHTML = cards([[s.mineral_types,'видов ископаемых'],[s.estimated_deposit_count ?? s.mineral_zone_count,'предполагаемых залежей'],[s.observed_mineral_cells,'ячеек с положительными пробами'],[s.interpolated_mineral_cells,'оценённых рудных ячеек']]);
        element('mineralResultsSummary').textContent = zones.length ? 'Зоны выделены по лабораторным анализам и сгруппированы в пространстве.' : 'Положительных проб, прошедших поисковые пороги, не найдено.';
        if(s.unplaced_target_count)element('mineralResultsSummary').textContent+=' · За границами сетки: '+s.unplaced_target_count+' интервалов (см. исходные цели).';
        element('reconstructionExtent').textContent = 'Участок '+fmt(d.width_m)+' × '+fmt(d.height_m)+' м · отметки от '+fmt(d.bottom_elevation_m)+' до '+fmt(d.top_elevation_m)+' м · ячейка '+fmt(dx)+' × '+fmt(dy)+' × '+fmt(dz)+' м. Глубже обследованного диапазона модель не строится.';
        const mode = element('reconstructionMode'), slider = element('reconstructionSlice'), layer = element('reconstructionLayer'), svg = element('reconstructionSvg');
        const first = zones[0]?.cells.find(c => c[1]===2)?.[0];
        const lastSlice = {xy:first == null ? Math.max(0,Math.floor(nz/3)) : coords(first)[2],xz:Math.floor(ny/2),yz:Math.floor(nx/2)};
        
        const supportLabels = {'-1':'Выше оценённой поверхности','0':'Нет данных','1':'Интерполировано','2':'Пересекает наблюдение'};
        function matching(i) {
          return (ore.get(i)||[]).filter(({zone}) => (!filter.value || zone.mineral_id===filter.value));
        }
        function voxelStyle(i) {
          const st = model.lithology_support[i], rock = model.rock_catalog[model.lithology[i]-1], match = matching(i);
          const mineral = match[0];
          if (layer.value==='support') return {fill:st===2?'#177e89':st===1?'#85c7bf':st===-1?'#ffffff':'#e1e5ea',opacity:1,stroke:'none'};
          if (mineral && layer.value!=='rocks') return {fill:mineral.zone.color, opacity:mineral.status===2?1:.52,stroke:mineral.status===2?'#263445':'none'};
          if (layer.value==='ore') return {fill:st===-1?'#fff':'#eef1f4',opacity:1,stroke:'none'};
          return {fill:rock?.color || (st===-1?'#fff':'#e1e5ea'),opacity:st===1?.6:1,stroke:st===2?'#64748b':'none'};
        }
        const legend = (color,label) => '<span><i style="background:'+escape(color)+'"></i>'+escape(label)+'</span>';
        function showCell(i) {
          const [x,y,z] = coords(i), r = model.rock_catalog[model.lithology[i]-1];
          const info = '<strong>X:</strong> '+fmt(x*dx)+'–'+fmt((x+1)*dx)+' м · <strong>Y:</strong> '+fmt(y*dy)+'–'+fmt((y+1)*dy)+' м<br><strong>Высота:</strong> '+fmt(d.top_elevation_m-(z+1)*dz)+'…'+fmt(d.top_elevation_m-z*dz)+' м<br><strong>Порода:</strong> '+escape(r?.name || 'не определена')+'<br><strong>Основание:</strong> '+supportLabels[model.lithology_support[i]];
          const finds = (ore.get(i)||[]).map(({zone,status}) => '<br><strong>'+escape(zone.analyte)+'</strong> · '+escape(zone.zone_id)+' · '+(status===2?'положительная проба пересекает ячейку':'интерполированное продолжение'));
          element('reconstructionCellInfo').innerHTML = info+finds.join('');
        }
        function drawVolume() {
          // Orthographic isometric projection of mineral voxels, with depth scaling.
          const width = d.width_m, height=d.height_m, depth=nz*dz;
          const raw = (x,y,z) => [(x-y)*.76,(x+y)*.36+z];
          const minX=-height*.76,maxX=width*.76, maxY=(width+height)*.36+depth;
          const scale=Math.min(620/(maxX-minX),410/maxY);
          const proj=(x,y,z)=>{const p=raw(x,y,z);return [(760-(maxX-minX)*scale)/2+(p[0]-minX)*scale,30+p[1]*scale];};
          const polygon=(points,fill,op,stroke,i)=>'<polygon points="'+points.map(p=>proj(...p).join(',')).join(' ')+'" fill="'+fill+'" fill-opacity="'+op+'" stroke="'+stroke+'" stroke-width=".6"'+(i==null?'':' data-voxel="'+i+'"')+'/>';
          let out=polygon([[0,0,0],[width,0,0],[width,height,0],[0,height,0]],'#eff5f9',.35,'#95a8b9',null);
          out+=polygon([[0,height,0],[width,height,0],[width,height,depth],[0,height,depth]],'none',1,'#a0b4c2',null);
          out+=polygon([[width,0,0],[width,height,0],[width,height,depth],[width,0,depth]],'none',1,'#a0b4c2',null);
          const showRocks=layer.value!=='ore', showOre=layer.value==='all'||layer.value==='ore';
          const volumeLegend=new Map();
          if(showRocks){
            const face=(i,points)=>{
              const st=model.lithology_support[i];
              if(st===-1)return '';
              const style=voxelStyle(i), rock=model.rock_catalog[model.lithology[i]-1];
              if(rock&&layer.value!=='support')volumeLegend.set(rock.name,rock.color);
              // Translucency in the combined view exposes the mineralized intersections.
              return polygon(points,layer.value==='all'?(rock?.color||'#e1e5ea'):style.fill,style.opacity*(layer.value==='all'?.18:1),'none',i);
            };
            // Outer geological faces plus topmost reconstructed cells at each X/Y.
            for(let iy=0;iy<ny;iy++)for(let ix=0;ix<nx;ix++){
              const x=ix*dx,y=iy*dy,X=x+dx,Y=y+dy;
              const elevation=model.surface_elevation_m[iy*nx+ix];
              let iz=elevation==null?0:Math.max(0,Math.min(nz-1,Math.floor((d.top_elevation_m-elevation)/dz)));
              while(iz<nz&&model.lithology_support[index(ix,iy,iz)]===-1)iz++;
              if(iz<nz){const z=iz*dz;out+=face(index(ix,iy,iz),[[x,y,z],[X,y,z],[X,Y,z],[x,Y,z]]);}
            }
            for(let iz=0;iz<nz;iz++){
              const z=iz*dz,Z=z+dz;
              for(let ix=0;ix<nx;ix++){const x=ix*dx,X=x+dx;out+=face(index(ix,ny-1,iz),[[x,height,z],[X,height,z],[X,height,Z],[x,height,Z]]);}
              for(let iy=0;iy<ny;iy++){const y=iy*dy,Y=y+dy;out+=face(index(nx-1,iy,iz),[[width,y,z],[width,Y,z],[width,Y,Z],[width,y,Z]]);}
            }
          }
          const sorted=(showOre?[...ore.keys()]:[]).filter(i=>matching(i).length).sort((a,b)=>{const [x,y,z]=coords(a),[X,Y,Z]=coords(b);return (x*dx+y*dy-z*dz)-(X*dx+Y*dy-Z*dz);});
          for(const i of sorted){
            const [ix,iy,iz]=coords(i), x=ix*dx,y=iy*dy,z=iz*dz, X=x+dx,Y=y+dy,Z=z+dz;
            const {zone,status}=matching(i)[0], c=zone.color, op=status===2?.95:.38;
            out+=polygon([[x,y,z],[X,y,z],[X,Y,z],[x,Y,z]],c,op,'#64748b',i);
            out+=polygon([[x,Y,z],[X,Y,z],[X,Y,Z],[x,Y,Z]],c,op*.8,'#64748b',i);
            out+=polygon([[X,y,z],[X,Y,z],[X,Y,Z],[X,y,Z]],c,op*.65,'#64748b',i);
          }
          if(showOre&&!sorted.length&&!showRocks) out+='<text x="380" y="240" text-anchor="middle" fill="#64748b">Нет рудных зон для отображения</text>';
          out+='<text x="22" y="470" fill="#486581" font-size="13">X '+fmt(width)+' м · Y '+fmt(height)+' м · диапазон отметок '+fmt(d.bottom_elevation_m)+'…'+fmt(d.top_elevation_m)+' м</text>';
          svg.innerHTML=out;
          element('reconstructionLegend').innerHTML=(layer.value==='support'?[legend('#177e89','Пересечение наблюдения'),legend('#85c7bf','Интерполяция')]:[...volumeLegend].map(([n,c])=>legend(c,n))).join('')+(showOre?minerals.filter(z=>!filter.value||filter.value===z.mineral_id).map(z=>legend(z.color,z.analyte)).join(''):'')+legend('#e1e5ea','Нет данных о породе');
        }
        function draw() {
          const view = mode.value || 'xy', slicing = ['xy','xz','yz'].includes(view);
          element('reconstructionSliceLabel').classList.toggle('hidden',!slicing);
          layer.disabled=!slicing&&view!=='3d';
          if(view==='3d'){drawVolume();return;}
          const k=lastSlice[view]||0, surfaceView=!slicing;
          const [cols,rows,realW,realH] = view==='xz' ? [nx,nz,d.width_m,nz*dz] : view==='yz' ? [ny,nz,d.height_m,nz*dz] : [nx,ny,d.width_m,d.height_m];
          const scale=Math.min(650/realW,410/realH), w=realW*scale,h=realH*scale, left=(760-w)/2,top=(490-h)/2;
          const rectW=w/cols,rectH=h/rows;
          let content='', colors=new Map();
          let values=surfaceView?(view==='terrain'?model.surface_elevation_m:model.geophysical_fields[view]?.values):null;
          const valid=values?.filter(v=>v!=null)||[], lo=valid.length?Math.min(...valid):0,hi=valid.length?Math.max(...valid):1;
          const pixels=[];
          for(let row=0;row<rows;row++) for(let col=0;col<cols;col++){
            const i=view==='xz'?index(col,k,row):view==='yz'?index(k,col,row):index(col,ny-1-row,surfaceView?0:k);
            let style,title;
            if(surfaceView){
              const v=values?.[i%plane], t=v==null?0.5:(v-lo)/Math.max(1e-9,hi-lo);
              style={fill:v==null?'#e1e5ea':'hsl('+Math.round(220-195*t)+' 65% '+Math.round(75-25*t)+'%)',opacity:1,stroke:'none'};
              title=v==null?'Нет наблюдений рядом':fmt(v)+' '+(view==='terrain'?'м':model.geophysical_fields[view].unit);
            }else{
              style=voxelStyle(i);const r=model.rock_catalog[model.lithology[i]-1];
              if(r&&layer.value!=='ore'&&layer.value!=='support')colors.set(r.name,r.color);
              title=(r?.name||'Неизвестно')+' · '+supportLabels[model.lithology_support[i]]+(matching(i).length?' · '+matching(i).map(e=>e.zone.analyte).join(', '):'');
            }
            pixels.push('<rect x="'+(left+col*rectW)+'" y="'+(top+row*rectH)+'" width="'+(rectW+.15)+'" height="'+(rectH+.15)+'" fill="'+style.fill+'" fill-opacity="'+style.opacity+'" stroke="'+style.stroke+'" stroke-width=".7" '+(surfaceView?'data-surface="'+i%plane+'"':'data-voxel="'+i+'"')+'><title>'+escape(title)+'</title></rect>');
          }
          content=pixels.join('')+'<rect x="'+left+'" y="'+top+'" width="'+w+'" height="'+h+'" fill="none" stroke="#8aa0af" pointer-events="none"/>';
          content+='<text x="'+left+'" y="'+(top-9)+'" font-size="12" fill="#486581">'+(view==='xz'||view==='yz'?'Отметка '+fmt(d.top_elevation_m)+' м':'Y '+fmt(d.height_m)+' м')+'</text>';
          content+='<text x="'+(left+w)+'" y="'+(top+h+18)+'" text-anchor="end" font-size="12" fill="#486581">'+(view==='yz'?'Y ':'X ')+fmt(realW)+' м</text>';
          if(view==='xz'||view==='yz')content+='<text x="'+left+'" y="'+(top+h+18)+'" font-size="12" fill="#486581">'+fmt(d.bottom_elevation_m)+' м</text>';
          svg.innerHTML=content;
          const legends=surfaceView?(valid.length?[legend('#b5c9eb',fmt(lo)),legend('#c66537',fmt(hi)+' '+(view==='terrain'?'м':model.geophysical_fields[view].unit)),legend('#e1e5ea','Нет данных')]:[legend('#e1e5ea','Нет данных')]):layer.value==='support'?[legend('#177e89','Пересечение наблюдения'),legend('#85c7bf','Интерполяция'),legend('#e1e5ea','Нет данных'),legend('#fff','Над поверхностью')]:[...colors].map(([n,c])=>legend(c,n)).concat(layer.value==='rocks'?[]:minerals.filter(z=>!filter.value||filter.value===z.mineral_id).map(z=>legend(z.color,z.analyte)),legend('#e1e5ea','Нет данных'),legend('#fff','Над поверхностью'));
          element('reconstructionLegend').innerHTML=legends.join('');
          if(slicing)element('reconstructionSliceCaption').textContent=view==='xy'?'Отметка '+fmt(d.top_elevation_m-(k+.5)*dz)+' м':(view==='xz'?'Y = '+fmt((k+.5)*dy):'X = '+fmt((k+.5)*dx))+' м';
        }
        function configureSlice(){
          const view=mode.value||'xy';
          const max={xy:nz-1,xz:ny-1,yz:nx-1}[view];
          if(max!=null){slider.max=String(max);slider.value=String(lastSlice[view]);}
          draw();
        }
        slider.addEventListener('input',()=>{lastSlice[mode.value||'xy']=Number(slider.value);draw();});
        mode.addEventListener('change',configureSlice);
        layer.addEventListener('change',draw);
        filter.addEventListener('change',draw);
        svg.addEventListener('click',event=>{
          const v=event.target.closest('[data-voxel]'), p=event.target.closest('[data-surface]');
          if(v){showCell(Number(v.dataset.voxel));return;}
          if(p){const i=Number(p.dataset.surface),view=mode.value,val=view==='terrain'?model.surface_elevation_m[i]:model.geophysical_fields[view].values[i];element('reconstructionCellInfo').textContent='X '+fmt((i%nx+.5)*dx)+' м · Y '+fmt((Math.floor(i/nx)+.5)*dy)+' м · '+(val==null?'Нет данных':fmt(val)+' '+(view==='terrain'?'м':model.geophysical_fields[view].unit));}
        });
        const labels={host_rock:'Вмещающая порода',observed_fault:'Разлом',steep_fault:'Крутой разлом',observed_contact:'Контакт пород',intrusive_rock:'Интрузия',compatible_core_properties:'Плотность и пористость',adjacent_positive_samples:'Смежные положительные пробы',nearby_soil_anomaly:'Почвенная аномалия',terrain_bauxite_depression:'Рельеф',terrain_exposed_host:'Обнажение',geophysics_magnetic:'Магнитная аномалия',geophysics_gamma:'Гамма-аномалия',downhole_gamma_anomaly:'Гамма-каротаж'};
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
          filter.value=z.mineral_id;mode.value='xy';layer.value='all';
          const i=z.cells.find(c=>c[1]===2)?.[0]??z.cells[0][0];lastSlice.xy=coords(i)[2];configureSlice();showCell(i);element('tab-recognized').click();
        });
        element('mineralAnomaliesSummary').textContent='Почвенных аномалий: '+model.soil_anomalies.length+' · геофизических аномалий: '+(result.geophysical_anomalies||[]).length;
        element('mineralAnomalyList').innerHTML=model.soil_anomalies.length?model.soil_anomalies.map(t=>'<tr><td>'+escape(t.site_id)+'</td><td>'+escape(t.analyte)+'</td><td>'+t.center_xyz_m.slice(0,2).map(fmt).join(' / ')+'</td><td>'+fmt(t.peak_result)+' / '+fmt(t.threshold)+' '+escape(t.unit)+'</td></tr>').join(''):'<tr><td colspan="4">Нет почвенных аномалий</td></tr>';
        element('downloadReconstructedMap').addEventListener('click',()=>download(JSON.stringify(model,null,2),'reconstructed_map.json','application/json'));
        element('openMineralResults').addEventListener('click',()=>element('tab-minerals').click());
        element('backToReconstruction').addEventListener('click',()=>element('tab-recognized').click());
        configureSlice();drawResults();
      }
'''
