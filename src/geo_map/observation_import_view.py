"""Controls shared by the preliminary and expedition observation sections."""

from pathlib import Path

IMPORT_ENGINE = Path(__file__).with_name('observation_import.js').read_text(encoding='utf-8')

IMPORT_STYLES = r'''
    .import-panel { border:1px solid var(--line); border-left:3px solid var(--highlight); background:var(--paper); padding:14px; margin:14px 0; }
    .import-panel h3 { margin:0 0 7px; font-size:14px; color:var(--ink); }
    .import-panel .data-downloads { align-items:stretch; margin-bottom:10px; }
    .import-panel .data-downloads button { flex:1 1 180px; width:auto; min-height:44px; display:flex; align-items:center; justify-content:center; text-align:center; padding:8px 12px; white-space:normal; overflow-wrap:anywhere; }
    .import-panel input[type="file"] { display:none; }
    .import-panel .import-status { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; margin:10px 0 0; color:var(--muted); }
    .import-panel .import-status[data-state="success"] { color:#17674a; }
    .import-panel .import-status[data-state="error"] { color:#ba3327; }
    .import-panel .import-status[data-state="duplicate"] { color:#87641f; }
'''

def import_panel(prefix: str) -> str:
    whole = '<label style="font-size:12px"><input id="fieldImportWhole" type="checkbox"> Импорт полного пакета JSON/XLSX</label>' if prefix == 'field' else ''
    return f'''
    <div class="import-panel" id="{prefix}ImportPanel">
      <h3>Ручная загрузка наблюдений</h3>
      <p class="muted" id="{prefix}ImportHint">Выберите файл для текущего типа наблюдений. Записи добавятся после проверки; существующие данные не перезаписываются.</p>
      <div class="data-downloads">
        <button type="button" id="{prefix}ImportTemplate">Скачать пустой CSV-шаблон</button>
        <button type="button" id="{prefix}ImportWorkbook">Шаблон Excel · XLSX</button>
        <button type="button" class="primary-button" id="{prefix}ImportChoose">Загрузить файл</button>
        <input id="{prefix}ImportFile" type="file" accept=".csv,.json,.geojson,.xlsx" aria-label="Загрузить наблюдения" hidden />
        <button type="button" id="{prefix}ImportExport">Скачать обновлённые наблюдения · JSON</button>
      </div>
      {whole}
      <p class="import-status" id="{prefix}ImportStatus" role="status" aria-live="polite">Выберите файл CSV, JSON, GeoJSON или XLSX.</p>
    </div>'''

IMPORT_UI = r'''
      // The standalone viewer persists imports only when the merged bundle is downloaded.
      let refreshFieldwork = () => {};
      let refreshPreliminary = () => {};
      function exportImportedObservations() {
        if(observations) download(JSON.stringify(observations,null,2), 'observations_imported.json', 'application/json');
      }
      function markRecognitionStale() {
        element('recognitionContent').classList.add('hidden');
        element('recognitionEmpty').classList.remove('hidden');
        element('recognitionEmpty').innerHTML='<h2>Наблюдения изменились</h2><p>Результаты предыдущего распознавания устарели. Скачайте объединённые наблюдения в разделах 02 или 03 и пересчитайте модель через recognize.py.</p>';
        element('mineralsContent').classList.add('hidden');
        element('mineralsEmpty').classList.remove('hidden');
        element('mineralsEmpty').innerHTML='<h2>Наблюдения изменились</h2><p>Обновите распознавание, чтобы получить найденные ископаемые на новых данных.</p>';
      }
      function setupImportControls(prefix, getTable, getAllowedTables, getSourceKind=()=>'', afterImport=()=>{}) {
        const input=element(prefix+'ImportFile'), status=element(prefix+'ImportStatus'), hint=element(prefix+'ImportHint');
        const panel=element(prefix+'ImportPanel');
        if(!observations){panel.classList.add('hidden');return ()=>{};}
        function updateHint(){
          const table=getTable(), fields=observations.table_fields[table];
          hint.textContent=(prefix==='field'&&element('fieldImportWhole').checked?'Выбран импорт всего пакета. ':'')+'Текущий шаблон: '+table+' · '+(fields?.length||0)+' полей · экспедиция '+observations.campaign.campaign_id+'. Пустые значения допустимы только в необязательных полях. Для связанных JSON/XLSX-пакетов проверяются все таблицы раздела.';
        }
        if(prefix==='field')element('fieldImportWhole').addEventListener('change',updateHint);
        element(prefix+'ImportTemplate').addEventListener('click',()=>{
          const table=getTable(),fields=observations.table_fields[table];
          if(fields)downloadCsv(fields,[],table+'_template.csv');
        });
        const workbookButton=element(prefix+'ImportWorkbook');
        workbookButton.disabled=!OBSERVATION_IMPORT_XLSX;
        workbookButton.addEventListener('click',()=>download(Uint8Array.from(atob(OBSERVATION_IMPORT_XLSX),ch=>ch.charCodeAt(0)),
          'manual_observations.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'));
        element(prefix+'ImportExport').addEventListener('click',exportImportedObservations);
        const chooseButton=element(prefix+'ImportChoose');
        chooseButton.addEventListener('click',()=>input.click());
        input.addEventListener('change',async()=>{
          const file=input.files?.[0];if(!file)return;
          // Capture the current selection before an asynchronous read completes.
          const table=getTable(),allowed=getAllowedTables(),kind=getSourceKind();
          input.disabled=true;chooseButton.disabled=true;
          status.dataset.state='';status.textContent='Проверяется файл '+file.name+'…';
          try{
            const payload=file.name.toLowerCase().endsWith('.xlsx')
              ? await ObservationImport.parseWorkbook(file,observations,allowed)
              : ObservationImport.parseText(file.name,await file.text(),table,observations);
            const result=ObservationImport.apply(observations,payload,{allowedTables:allowed,rockReference:OBSERVATION_IMPORT_ROCKS,sourceKind:kind,filename:file.name});
            let renderingWarning='';
            if(result.added){
              if (EXPEDITION_COLLECTED) markRecognitionStale();
              try {refreshFieldwork();refreshPreliminary();afterImport();}
              catch(error){renderingWarning='\nДанные приняты, но не удалось обновить отображение: '+error.message+'. Скачайте объединённый JSON.';}
            }
            status.dataset.state=result.added?'success':'duplicate';
            const detail=Object.entries(result.byTable).map(([name,v])=>name+': добавлено '+v.added+', повторов '+v.duplicates).join('\n');
            status.textContent=(result.added?'Файл принят. Добавлено записей: '+result.added+'. Точных повторов пропущено: '+result.duplicates+'.':'Файл уже представлен в наблюдениях. Все '+result.duplicates+' записей — точные дубликаты; данные не изменены.')+'\n'+detail+(result.added?(!EXPEDITION_COLLECTED&&EXPEDITION_ENDPOINT?'\nНовые наблюдения будут использованы при запуске экспедиции на вкладке 03.':'\nСохраните обновлённый JSON, чтобы использовать новые наблюдения после закрытия страницы.'):'')+renderingWarning;
          }catch(error){
            status.dataset.state='error';status.textContent='Файл отклонён: '+error.message+'\nНаблюдения не изменены.';
          }finally{input.disabled=false;chooseButton.disabled=false;input.value='';}
        });
        updateHint();
        return updateHint;
      }
'''
