/* Strict, transactional observation import for the offline expedition workspace. */
const ObservationImport = (() => {
  const keys = {
    borehole_collars:['hole_id'], borehole_lithology:['interval_id'],
    borehole_assays:['sample_id','analyte'], downhole_properties:['measurement_id'],
    downhole_gamma:['measurement_id'], downhole_magnetic:['measurement_id'], structural_observations:['observation_id'],
    surface_geochemistry:['sample_id','analyte'], outcrop_observations:['observation_id'],
    terrain_observations:['observation_id'], magnetic_observations:['observation_id'],
    gamma_observations:['observation_id'], trenches:['trench_id'],
    trench_intervals:['interval_id'], trench_samples:['sample_id','analyte'],
    fault_intersections:['observation_id'], quality_control:['control_id'],
  };
  const pointTables = ['surface_geochemistry','outcrop_observations','terrain_observations','magnetic_observations','gamma_observations'];
  const boreholeTables = ['borehole_collars','borehole_lithology','borehole_assays','downhole_properties','structural_observations','fault_intersections','downhole_gamma','downhole_magnetic'];
  const sampleTables = ['borehole_assays','trench_samples','surface_geochemistry'];
  const assayTables = [...sampleTables,'quality_control'];
  const required = {
    borehole_collars:'hole_id x_m y_m collar_elevation_m total_depth_m azimuth_deg dip_deg coordinate_system position_uncertainty_m drilling_method start_date hole_status',
    borehole_lithology:'hole_id interval_id from_m to_m observed_rock_id observed_rock_name confidence observer logged_date',
    borehole_assays:'sample_id hole_id from_m to_m analyte result_value unit detection_limit analysis_method laboratory certificate_id qc_type qc_flag',
    downhole_properties:'hole_id measurement_id measurement_method qc_flag',
    downhole_gamma:'hole_id measurement_id from_m to_m depth_m gamma_count_rate_cps gamma_sigma_cps counting_time_s measurement_method logged_date',
    downhole_magnetic:'hole_id measurement_id from_m to_m depth_m magnetic_susceptibility_si magnetic_sigma_si measurement_method logged_date',
    structural_observations:'observation_id feature_type confidence observation_method',
    surface_geochemistry:'sample_id x_m y_m sample_date sample_material sampling_depth_from_m sampling_depth_to_m sampling_method analyte result_value unit detection_limit analysis_method laboratory certificate_id position_uncertainty_m qc_type qc_flag',
    outcrop_observations:'observation_id x_m y_m surface_elevation_m observed_rock_id observed_rock_name observation_method position_uncertainty_m survey_date',
    terrain_observations:'observation_id x_m y_m surface_elevation_m elevation_uncertainty_m terrain_type observation_method survey_date',
    magnetic_observations:'observation_id station_id x_m y_m surface_elevation_m magnetic_anomaly_nt magnetic_sigma_nt position_uncertainty_m observation_method survey_date',
    gamma_observations:'observation_id station_id x_m y_m surface_elevation_m gamma_count_rate_cps gamma_sigma_cps position_uncertainty_m observation_method survey_date',
    trenches:'trench_id start_x_m start_y_m end_x_m end_y_m depth_m width_m surveyed_length_m position_uncertainty_m trench_status survey_date',
    trench_intervals:'trench_id interval_id from_m to_m observed_rock_id observed_rock_name sample_material confidence',
    trench_samples:'trench_id sample_id from_m to_m sampling_depth_from_m sampling_depth_to_m sample_material sampling_method analyte result_value unit detection_limit analysis_method laboratory certificate_id qc_type qc_flag',
    fault_intersections:'observation_id hole_id from_m to_m observation_method confidence',
    quality_control:'control_id sample_id sample_source qc_type analyte result_value unit detection_limit acceptance_limit acceptance_unit qc_flag',
  };
  const categories = {
    coordinate_system:['local_cartesian'], hole_status:['planned','in_progress','completed','abandoned'],
    trench_status:['planned','in_progress','completed','abandoned','backfilled'],
    confidence:['low','medium','high'], weathering:['fresh','slight','moderate','strong','complete'],
    qc_type:['primary','duplicate','blank','standard'], qc_flag:['not_checked','pass','warning','fail'],
    result_qualifier:['eq','lt','gt','estimated'], feature_type:['bedding','contact','fracture','fault','vein','foliation'],
    terrain_type:['flat','slope','hill','depression','undetermined'],
    sample_material:['soil','rock','regolith'], sample_source:['borehole','trench','surface'],
  };
  const numbers = new Set('x_m y_m collar_elevation_m total_depth_m azimuth_deg dip_deg position_uncertainty_m from_m to_m depth_m density_g_cm3 porosity_percent density_error_g_cm3 porosity_error_percent strike_deg dip_direction_deg offset_estimate_m sampling_depth_from_m sampling_depth_to_m result_value detection_limit surface_elevation_m elevation_uncertainty_m slope_deg local_relief_m magnetic_anomaly_nt magnetic_sigma_nt magnetic_susceptibility_si magnetic_sigma_si gamma_count_rate_cps gamma_sigma_cps counting_time_s start_x_m start_y_m end_x_m end_y_m width_m surveyed_length_m reference_value reference_uncertainty absolute_difference relative_difference_percent acceptance_limit'.split(' '));
  const signed = new Set('x_m y_m start_x_m start_y_m end_x_m end_y_m collar_elevation_m surface_elevation_m magnetic_anomaly_nt magnetic_susceptibility_si local_relief_m dip_deg offset_estimate_m absolute_difference relative_difference_percent'.split(' '));
  const fail = message => { throw new Error(message); };
  const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const recordKey = (table,row) => JSON.stringify(keys[table].map(k=>row[k]));
  const canonical = value => missing(value)?null:typeof value==='string'?value.trim():value;
  const rowEqual = (a,b,fields) => fields.every(k=>canonical(a[k])===canonical(b[k]));
  const label = (table,row) => keys[table].map(k=>row[k]).join(' / ');
  const missing = value => value === null || value === undefined || value === '';
  const assert = (condition,message) => { if(!condition)fail(message); };
  const dateField = field => field==='survey_date'||field==='sample_date'||field==='logged_date'||field==='start_date'||field==='end_date';
  function validDate(value) {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
    const d=new Date(value+'T00:00:00Z');
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0,10)===value;
  }
  function fieldSet(actual, expected, context) {
    const unknown=actual.filter(f=>!expected.includes(f)), absent=expected.filter(f=>!actual.includes(f));
    assert(new Set(actual).size===actual.length, context+': повторяющиеся названия столбцов');
    assert(!unknown.length&&!absent.length, context+': не соответствует шаблону'+
      (absent.length?'; отсутствуют: '+absent.join(', '):'')+(unknown.length?'; лишние: '+unknown.join(', '):''));
  }
  // RFC 4180 quoting (including embedded commas, escaped quotes and line breaks).
  // A semicolon-delimited UTF-8 export from a local spreadsheet is also accepted.
  function csvRows(text, expected) {
    text=text.replace(/^\uFEFF/,'');
    let delimiter=',', quoted=false, first='';
    for(let i=0;i<text.length;i++){
      const ch=text[i];
      if(ch==='"')quoted=!quoted;
      if(!quoted&&(ch==='\n'||ch==='\r'))break;
      first+=ch;
    }
    if(first.includes(';')&&!first.includes(','))delimiter=';';
    const rows=[];
    let row=[], value='', inQuotes=false, closed=false;
    function pushField(){row.push(value);value='';closed=false;}
    function pushRow(){pushField();if(row.some(v=>v.trim()!==''))rows.push(row);row=[];}
    for(let i=0;i<text.length;i++){
      const ch=text[i];
      if(inQuotes){
        if(ch==='"'){
          if(text[i+1]==='"'){value+='"';i++;}
          else{inQuotes=false;closed=true;}
        }else value+=ch;
      }else if(ch===delimiter){pushField();}
      else if(ch==='\r'||ch==='\n'){if(ch==='\r'&&text[i+1]==='\n')i++;pushRow();}
      else if(ch==='"'&&value===''&&!closed){inQuotes=true;}
      else {assert(!closed&&ch!=='"','CSV: неверное экранирование кавычек');value+=ch;}
    }
    assert(!inQuotes,'CSV: незакрытая кавычка');
    if(row.length||value!==''||closed)pushRow();
    assert(rows.length,'CSV: отсутствует заголовок');
    const header=rows.shift().map(v=>v.trim());
    fieldSet(header,expected,'CSV, заголовок');
    return rows.map((values,i)=>{
      assert(values.length===header.length,'CSV, запись '+(i+2)+': неверное число столбцов');
      return Object.fromEntries(header.map((f,j)=>[f,delimiter===';'&&numbers.has(f)?values[j].replace(',','.'):values[j]]));
    });
  }
  function geoRows(data,table,bundle) {
    const name=table==='trenches'?'trench_paths':table;
    assert(pointTables.includes(table)||table==='trenches','GeoJSON не поддерживается для выбранной таблицы');
    assert(data.type==='FeatureCollection'&&Array.isArray(data.features),'Ожидается GeoJSON FeatureCollection');
    assert(!data.name||data.name===name,'Слой GeoJSON не соответствует выбранному типу: '+name);
    assert(data.coordinate_system===bundle.campaign.coordinate_system,'Укажите локальную систему координат экспедиции в GeoJSON');
    assert(data.coordinate_unit==='m','Координаты GeoJSON должны быть в метрах');
    if(data.map_extent_m){
      assert(JSON.stringify(data.map_extent_m.x)===JSON.stringify([0,bundle.campaign.width_m])&&JSON.stringify(data.map_extent_m.y)===JSON.stringify([0,bundle.campaign.height_m]),'Границы GeoJSON не совпадают с участком экспедиции');
    }
    return data.features.map((feature,i)=>{
      assert(feature.type==='Feature'&&isObject(feature.properties)&&isObject(feature.geometry),'GeoJSON: неверный Feature №'+(i+1));
      const row={...feature.properties}, geom=feature.geometry;
      function assign(field,value){
        assert(typeof value==='number'&&Number.isFinite(value),'GeoJSON: неверная координата '+field);
        assert(!Object.hasOwn(row,field)||row[field]===value,'GeoJSON: координаты геометрии противоречат полям '+field);
        row[field]=value;
      }
      if(table==='trenches'){
        assert(geom.type==='LineString'&&Array.isArray(geom.coordinates)&&geom.coordinates.length===2&&geom.coordinates.every(p=>Array.isArray(p)&&p.length===2),'GeoJSON: требуется отрезок LineString из двух точек');
        assign('start_x_m',geom.coordinates[0][0]);assign('start_y_m',geom.coordinates[0][1]);
        assign('end_x_m',geom.coordinates[1][0]);assign('end_y_m',geom.coordinates[1][1]);
      }else{
        assert(geom.type==='Point'&&Array.isArray(geom.coordinates)&&geom.coordinates.length===2,'GeoJSON: требуется Point [X,Y]');
        assign('x_m',geom.coordinates[0]);assign('y_m',geom.coordinates[1]);
      }
      const expectedId=table==='surface_geochemistry'?row.sample_id+'-'+row.analyte:table==='trenches'?row.trench_id:row.observation_id;
      assert(feature.id==null||feature.id===expectedId,'GeoJSON: ID объекта не совпадает с идентификатором записи');
      return row;
    });
  }
  function parseText(filename,text,selectedTable,bundle) {
    const ext=filename.toLowerCase().split('.').pop();
    if(ext==='csv'){
      assert(bundle.table_fields[selectedTable],'Выберите тип наблюдений для CSV');
      return {tables:{[selectedTable]:csvRows(text,bundle.table_fields[selectedTable])},textValues:true};
    }
    assert(ext==='json'||ext==='geojson','Неподдерживаемый формат. Используйте CSV, JSON, GeoJSON или XLSX по шаблону.');
    let data;
    try {data=JSON.parse(text.replace(/^\uFEFF/,''));}catch{fail('JSON: файл не является корректным JSON');}
    if(data?.type==='FeatureCollection'||ext==='geojson')return {tables:{[selectedTable]:geoRows(data,selectedTable,bundle)},textValues:false};
    if(Array.isArray(data))return {tables:{[selectedTable]:data},textValues:false};
    assert(isObject(data),'JSON: ожидается объект или массив строк');
    if(data.tables){
      assert(isObject(data.tables),'JSON: tables должен быть объектом таблиц');
      assert(!data.campaign_id||data.campaign_id===bundle.campaign.campaign_id,'Файл относится к другой экспедиции');
      if(data.campaign){
        assert(data.campaign.campaign_id===bundle.campaign.campaign_id,'Файл относится к другой экспедиции');
        for(const f of ['width_m','height_m','coordinate_system'])if(data.campaign[f]!=null)assert(data.campaign[f]===bundle.campaign[f],'Параметр кампании '+f+' не совпадает');
      }
      if(data.table_fields){
        for(const [table,fields] of Object.entries(data.table_fields)){
          assert(bundle.table_fields[table]&&Array.isArray(fields),'Неизвестная схема таблицы '+table);
          fieldSet(fields,bundle.table_fields[table],table);
        }
      }
      return {tables:data.tables,textValues:false,sourceKind:data.source?.kind};
    }
    if(data.rows){
      assert(!data.table||data.table===selectedTable,'Таблица JSON не соответствует выбранному типу');
      return {tables:{[selectedTable]:data.rows},textValues:false};
    }
    return {tables:{[selectedTable]:[data]},textValues:false};
  }

  // Read ordinary Open XML workbooks locally. Do not evaluate formula cells
  // or follow external relationships. Spreadsheet headers use the CSV schema.
  async function parseWorkbook(file,bundle,allowedTables) {
    const buffer=await file.arrayBuffer(), bytes=new Uint8Array(buffer), view=new DataView(buffer);
    const decoder=new TextDecoder('utf-8',{fatal:true});
    const u16=i=>view.getUint16(i,true),u32=i=>view.getUint32(i,true);
    let end=-1;
    for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--)if(u32(i)===0x06054b50){end=i;break;}
    assert(end>=0,'XLSX: файл не является обычным ZIP-контейнером Excel');
    const count=u16(end+10),offset=u32(end+16),entries=new Map();
    let p=offset;
    for(let i=0;i<count;i++){
      assert(p+46<=bytes.length&&u32(p)===0x02014b50,'XLSX: повреждён каталог ZIP');
      const nameLength=u16(p+28),extra=u16(p+30),comment=u16(p+32),name=decoder.decode(bytes.subarray(p+46,p+46+nameLength));
      entries.set(name,{flag:u16(p+8),method:u16(p+10),size:u32(p+20),expanded:u32(p+24),start:u32(p+42)});
      p+=46+nameLength+extra+comment;
    }
    async function extract(name){
      const entry=entries.get(name);
      assert(entry,'XLSX: отсутствует часть '+name);
      assert(!(entry.flag&1),'XLSX: зашифрованные книги не поддерживаются');
      assert(entry.expanded<=64*1024*1024,'XLSX: слишком большой XML-лист');
      const i=entry.start;
      assert(i+30<=bytes.length&&u32(i)===0x04034b50,'XLSX: повреждён локальный заголовок');
      const start=i+30+u16(i+26)+u16(i+28);
      assert(start+entry.size<=bytes.length,'XLSX: повреждён размер ZIP');
      const data=bytes.slice(start,start+entry.size);
      if(entry.method===0)return decoder.decode(data);
      assert(entry.method===8,'XLSX: неподдерживаемый метод упаковки');
      assert(typeof DecompressionStream!=='undefined','Браузер не поддерживает распаковку XLSX. Сохраните лист как CSV.');
      let text;
      try {
        const reader=new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
        const chunks=[];let length=0;
        for(;;){const {value,done}=await reader.read();if(done)break;length+=value.length;
          if(length>entry.expanded||length>64*1024*1024){await reader.cancel();fail('XLSX: неверный размер распакованного листа');}
          chunks.push(value);}
        assert(length===entry.expanded,'XLSX: неверный размер распакованного листа');
        text=await new Blob(chunks).text();
      }catch(error){fail('XLSX: не удалось распаковать '+name+'. '+error.message+'; попробуйте CSV.');}
      return text;
    }
    const xml=async name=>{
      const text=await extract(name);
      assert(!/<!DOCTYPE|<!ENTITY/i.test(text),'XLSX: неподдерживаемое объявление XML');
      const doc=new DOMParser().parseFromString(text,'application/xml');
      assert(!doc.getElementsByTagName('parsererror').length,'XLSX: некорректный XML '+name);
      return doc;
    };
    const tags=(node,name)=>Array.from(node.getElementsByTagNameNS('*',name));
    const text=(node,name)=>tags(node,name).map(n=>n.textContent).join('');
    const book=await xml('xl/workbook.xml'), relations=await xml('xl/_rels/workbook.xml.rels');
    const date1904=['1','true'].includes(tags(book,'workbookPr')[0]?.getAttribute('date1904'));
    const targets=new Map(tags(relations,'Relationship').filter(r=>r.getAttribute('TargetMode')!=='External').map(r=>[r.getAttribute('Id'),r.getAttribute('Target')]));
    const shared=entries.has('xl/sharedStrings.xml')?tags(await xml('xl/sharedStrings.xml'),'si').map(n=>text(n,'t')):[];
    const alias={Collars:'borehole_collars',Lithology:'borehole_lithology',Assays:'borehole_assays',Properties:'downhole_properties',Structures:'structural_observations',QAQC:'quality_control',Trenches:'trenches',Intervals:'trench_intervals',Samples:'trench_samples'};
    const tables={};
    for(const sheet of tags(book,'sheet')){
      const name=sheet.getAttribute('name'),table=Object.hasOwn(bundle.table_fields,name)?name:alias[name];
      if(!table){
        if(['Instructions','RockCodes','Analytes','Codebook'].includes(name))continue;
        fail('XLSX: неизвестный лист '+name);
      }
      const rid=sheet.getAttribute('r:id')||sheet.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships','id');
      let target=targets.get(rid);
      assert(target,'XLSX: отсутствует внутренний лист '+name);
      target=target.startsWith('/')?target.slice(1):'xl/'+target;
      assert(target.startsWith('xl/worksheets/')&&!target.includes('..'),'XLSX: неверный путь листа');
      const doc=await xml(target), rows=[];
      for(const row of tags(doc,'row')){
        const values=[];
        for(const cell of tags(row,'c')){
          const ref=cell.getAttribute('r'),match=/^([A-Z]+)[0-9]+$/.exec(ref||'');
          assert(match,'XLSX: неверная ссылка ячейки');
          let index=0;for(const letter of match[1])index=index*26+letter.charCodeAt(0)-64;
          assert(index<=16384,'XLSX: слишком много столбцов');
          assert(!tags(cell,'f').length,'XLSX: формулы не допускаются, сохраните значения');
          const type=cell.getAttribute('t'),value=text(cell,'v');
          assert(type!=='e','XLSX: ошибка в ячейке '+ref);
          if(type==='s')assert(shared[Number(value)]!==undefined,'XLSX: повреждена общая строка');
          values[index-1]=type==='s'?shared[Number(value)]:type==='inlineStr'?text(cell,'t'):value;
        }
        if(values.some(v=>v!=null&&v!==''))rows.push(values);
      }
      if(!rows.length)continue;
      const header=Array.from(rows.shift(),v=>(v??'').trim());
      // Blank data sheets outside the active section do not affect import.
      if(!rows.length&&!allowedTables.includes(table))continue;
      fieldSet(header,bundle.table_fields[table],'Лист '+name);
      assert(!Object.hasOwn(tables,table),'XLSX: несколько листов для таблицы '+table);
      tables[table]=rows.map((row,i)=>{
        assert(row.length<=header.length,'Лист '+name+', строка '+(i+2)+': лишние столбцы');
        return Object.fromEntries(header.map((field,j)=>{
          let value=row[j]??'';
          if(dateField(field)&&/^\d+(?:\.0+)?$/.test(value)){
            assert(Number(value)>=(date1904?0:61)&&Number(value)<=(date1904?2957003:2958465),'XLSX: недопустимая дата Excel');
            value=new Date((date1904?Date.UTC(1904,0,1):Date.UTC(1899,11,30))+Number(value)*86400000).toISOString().slice(0,10);
          }
          return [field,value];
        }));
      });
    }
    return {tables,textValues:true};
  }

  function normalize(table,row,fields,textValues) {
    assert(isObject(row),'ожидается объект записи');
    fieldSet(Object.keys(row),fields,'Поля');
    const result={};
    for(const field of fields){
      let value=row[field];
      if(missing(value)||typeof value==='string'&&value.trim()===''){result[field]=null;continue;}
      if(numbers.has(field)){
        if(textValues&&typeof value==='string'){
          value=value.trim();
          assert(/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value),field+': ожидается число');
          value=Number(value);
        }
        assert(typeof value==='number'&&Number.isFinite(value),field+': ожидается конечное число');
      }else{
        assert(typeof value==='string',field+': ожидается строка');
        value=value.trim();
        assert(!['NaN','Inf','Infinity','N/A','-999'].includes(value),field+': неизвестное значение следует оставить пустым');
      }
      result[field]=value;
    }
    for(const f of ['campaign_id',...keys[table],...required[table].split(' ')]){
      assert(!missing(result[f]),f+': обязательное поле');
    }
    return result;
  }
  function validate(bundle, table, row, ctx) {
    assert(row.campaign_id===bundle.campaign.campaign_id,'campaign_id: ожидается '+bundle.campaign.campaign_id);
    for(const [f,value] of Object.entries(row)){
      if(value==null)continue;
      if(numbers.has(f)){
        if(!signed.has(f))assert(value>=0,f+': значение не может быть отрицательным');
        assert(value!==-999,f+': условные значения пропусков запрещены');
      }
      if(categories[f])assert(categories[f].includes(value),f+': недопустимое значение '+value);
      if(dateField(f))assert(validDate(value),f+': дата должна быть реальной датой YYYY-MM-DD');
    }
    const bounded=(field,lo,hi,exclusive=false)=>{if(row[field]!=null)assert(row[field]>=lo&&(exclusive?row[field]<hi:row[field]<=hi),field+': допустимый диапазон '+lo+'…'+hi);};
    const positive=field=>{if(row[field]!=null)assert(row[field]>0,field+': ожидается положительное значение');};
    const tolerance=row.position_uncertainty_m||0;
    function xy(x,y){
      assert(typeof x==='number'&&typeof y==='number','Нужны обе координаты X и Y');
      assert(x>=-tolerance&&x<=bundle.campaign.width_m+tolerance&&y>=-tolerance&&y<=bundle.campaign.height_m+tolerance,'Координаты за пределами участка с учётом погрешности');
    }
    function interval(start,end,limit){
      assert(typeof start==='number'&&typeof end==='number'&&start>=0&&start<end&&(limit==null||end<=limit+1e-6),'Неверный интервал: 0 ≤ from < to ≤ длины объекта');
    }
    function depth(value,limit){assert(typeof value==='number'&&value>=0&&value<=limit+1e-6,'Глубина вне границ скважины');}
    if(row.observed_rock_id){
      const rock=ctx.rocks.get(row.observed_rock_id);
      assert(rock,'Неизвестная порода '+row.observed_rock_id);
      assert(row.observed_rock_name===rock.name,'Название породы не совпадает с кодом '+row.observed_rock_id);
    }
    if(assayTables.includes(table)){
      const units=ctx.analytes.get(row.analyte);
      assert(units?.has(row.unit),'Неизвестный аналит или неверная единица: '+row.analyte+' / '+row.unit);
      positive('detection_limit');
      if(row.unit.startsWith('%'))bounded('result_value',0,100);
      if(row.result_qualifier==='lt')assert(row.result_value<=row.detection_limit+1e-9,'Результат lt превышает предел обнаружения');
      if(sampleTables.includes(table))assert(row.qc_type==='primary','Контрольные пробы загружаются в таблицу Контроль качества');
    }
    if(table==='borehole_collars'){
      xy(row.x_m,row.y_m);positive('total_depth_m');bounded('azimuth_deg',0,360,true);bounded('dip_deg',-90,0,true);
      if(row.end_date)assert(row.end_date>=row.start_date,'Дата окончания раньше начала');
      if(row.hole_status==='completed')assert(row.end_date,'Для завершённой скважины нужна дата окончания');
      const angle=row.dip_deg*Math.PI/180, azimuth=row.azimuth_deg*Math.PI/180, horizontal=row.total_depth_m*Math.cos(angle);
      xy(row.x_m+horizontal*Math.sin(azimuth),row.y_m+horizontal*Math.cos(azimuth));
    }
    if(table==='trenches'){
      xy(row.start_x_m,row.start_y_m);xy(row.end_x_m,row.end_y_m);
      for(const f of ['depth_m','width_m','surveyed_length_m'])positive(f);
      const length=Math.hypot(row.end_x_m-row.start_x_m,row.end_y_m-row.start_y_m);
      assert(Math.abs(length-row.surveyed_length_m)<=Math.max(1e-5,2*tolerance),'Длина траншеи не совпадает с указанными координатами');
    }
    if(pointTables.includes(table))xy(row.x_m,row.y_m);
    if(table==='terrain_observations')bounded('slope_deg',0,90);
    if(row.hole_id&&table!=='borehole_collars'){
      const hole=ctx.holes.get(row.hole_id);
      assert(hole,'Неизвестная скважина '+row.hole_id+'; сначала загрузите её паспорт');
      if(row.from_m!=null||row.to_m!=null)interval(row.from_m,row.to_m,hole.total_depth_m);
      if(row.depth_m!=null)depth(row.depth_m,hole.total_depth_m);
    }
    if(row.trench_id&&table!=='trenches'){
      const trench=ctx.trenches.get(row.trench_id);
      assert(trench,'Неизвестная траншея '+row.trench_id+'; сначала загрузите её паспорт');
      if(row.from_m!=null||row.to_m!=null)interval(row.from_m,row.to_m,trench.surveyed_length_m);
      if(table==='trench_samples')interval(row.sampling_depth_from_m,row.sampling_depth_to_m,trench.depth_m);
    }
    if(table==='surface_geochemistry'){
      interval(row.sampling_depth_from_m,row.sampling_depth_to_m,null);
      assert(!row.parent_sample_id,'Первичная проба не должна иметь parent_sample_id');
    }
    if(table==='downhole_properties'){
      const point=row.depth_m!=null, span=row.from_m!=null&&row.to_m!=null;
      assert(point!==span&&!(point&&(row.from_m!=null||row.to_m!=null)),'Укажите либо точечную глубину, либо две границы интервала');
      assert(row.density_g_cm3!=null||row.porosity_percent!=null,'Нужна плотность или пористость');
      positive('density_g_cm3');bounded('porosity_percent',0,100);
    }
    if(table==='downhole_gamma'){
      positive('counting_time_s');
      assert(Math.abs(row.depth_m-(row.from_m+row.to_m)/2)<=1e-5,'depth_m: должна быть середина интервала');
    }
    if(table==='downhole_magnetic'){
      assert(Math.abs(row.depth_m-(row.from_m+row.to_m)/2)<=1e-5,'depth_m: должна быть середина интервала');
    }
    if(table==='structural_observations'){
      if(row.hole_id)assert(row.depth_m!=null,'Для скважинной структуры нужна depth_m');
      else {xy(row.x_m,row.y_m);assert(row.depth_m==null,'Для поверхностной структуры не указывается скважинная глубина');}
      assert((row.x_m==null)===(row.y_m==null),'Укажите обе координаты или оставьте обе пустыми');
      if(row.x_m!=null)xy(row.x_m,row.y_m);
      bounded('strike_deg',0,360,true);bounded('dip_direction_deg',0,360,true);bounded('dip_deg',0,90);
    }
    if(table==='fault_intersections'){
      const structure=ctx.structures.get(row.observation_id);
      assert(structure?.feature_type==='fault'&&structure.hole_id===row.hole_id,'Интервал разлома должен ссылаться на наблюдение fault этой скважины');
      if(structure.depth_m!=null)assert(structure.depth_m>=row.from_m-1e-6&&structure.depth_m<=row.to_m+1e-6,'Глубина наблюдения разлома вне интервала');
    }
    if(table==='quality_control'){
      assert(!ctx.samples.has(row.sample_id),'Идентификатор контрольной пробы совпадает с первичной пробой');
      assert(!ctx.controls.some(other=>other!==row&&other.sample_id===row.sample_id&&other.analyte===row.analyte),'Повторный аналит контрольной пробы');
      assert(row.qc_type!=='primary','В таблице контроля качества допускаются duplicate, blank и standard');
      const sourceField={borehole:'hole_id',trench:'trench_id',surface:null}[row.sample_source];
      if(sourceField)assert(row[sourceField],'Для источника '+row.sample_source+' нужна ссылка '+sourceField);
      if(row.sample_source!=='borehole')assert(!row.hole_id,'Лишняя ссылка hole_id для выбранного источника');
      if(row.sample_source!=='trench')assert(!row.trench_id,'Лишняя ссылка trench_id для выбранного источника');
      assert(row.acceptance_unit==='%'||row.acceptance_unit===row.unit,'Единица допуска контроля должна соответствовать аналиту или процентам');
      const sameControl=ctx.controls.filter(other=>other!==row&&other.sample_id===row.sample_id);
      assert(sameControl.every(other=>['sample_source','hole_id','trench_id','qc_type','parent_sample_id'].every(f=>(other[f]??null)===(row[f]??null))),'Разные источники или типы контроля у одного идентификатора контрольной пробы');
      if(row.qc_type==='duplicate'){
        assert(row.parent_sample_id,'Для дубликата нужна исходная проба');
        const parent=ctx.samples.get(row.parent_sample_id);
        assert(parent&&parent.source===row.sample_source&&parent[sourceField]===row[sourceField]&&parent.analytes.has(row.analyte+'\0'+row.unit),'Исходная проба или аналит не найдены либо принадлежат другому объекту');
      }
      if(row.qc_type==='standard')assert(row.reference_value!=null,'Для стандарта нужно контрольное значение');
      if(row.qc_type!=='duplicate')assert(!row.parent_sample_id,'Ссылка на исходную пробу допустима только для дубликата');
    }
  }
  function sampleRegistry(tables) {
    const registry=new Map();
    for(const table of sampleTables){
      const source={borehole_assays:'borehole',trench_samples:'trench',surface_geochemistry:'surface'}[table];
      for(const row of (tables[table]||[])){
        const shared=['hole_id','trench_id','from_m','to_m','x_m','y_m','sample_date','sample_material','sampling_depth_from_m','sampling_depth_to_m','sampling_method'];
        const record={source,...Object.fromEntries(shared.map(f=>[f,row[f]??null])),analytes:new Set()};
        const previous=registry.get(row.sample_id);
        if(previous){
          assert(previous.source===source&&shared.every(f=>previous[f]===record[f]),'Проба '+row.sample_id+': разные координаты, интервалы, материал или источник у одного идентификатора');
        }else registry.set(row.sample_id,record);
        registry.get(row.sample_id).analytes.add(row.analyte+'\0'+row.unit);
      }
    }
    return registry;
  }
  function geojsonLayer(bundle,table) {
    const name=table==='trenches'?'trench_paths':table;
    const common={type:'FeatureCollection',schema_version:'1.0',name,coordinate_system:bundle.campaign.coordinate_system,
      coordinate_unit:'m',map_extent_m:{x:[0,bundle.campaign.width_m],y:[0,bundle.campaign.height_m]}};
    if(table==='surface_geochemistry')common.vertical_reference='depth_positive_down_from_surface';
    return {...common,features:bundle.tables[table].map(row=>{
      if(table==='trenches')return {type:'Feature',id:row.trench_id,geometry:{type:'LineString',coordinates:[[row.start_x_m,row.start_y_m],[row.end_x_m,row.end_y_m]]},properties:{...row}};
      const {x_m,y_m,...properties}=row;
      return {type:'Feature',id:table==='surface_geochemistry'?row.sample_id+'-'+row.analyte:row.observation_id,geometry:{type:'Point',coordinates:[x_m,y_m]},properties};
    })};
  }
  function refreshMetadata(bundle, changed, rocks) {
    const t=bundle.tables, s=bundle.summary, unique=(rows,key)=>new Set(rows.map(r=>r[key])).size;
    const summarizeHoles=rows=>{
      const ids=new Set(rows.map(r=>r.hole_id)), selected=name=>(t[name]||[]).filter(r=>ids.has(r.hole_id));
      return {hole_count:rows.length,drilled_m:Number(rows.reduce((n,r)=>n+r.total_depth_m,0).toFixed(6)),
        sample_count:unique(selected('borehole_assays'),'sample_id'),assay_count:selected('borehole_assays').length,
        lithology_count:selected('borehole_lithology').length,property_count:selected('downhole_properties').length,
        gamma_log_count:selected('downhole_gamma').length,magnetic_log_count:selected('downhole_magnetic').length,contact_count:selected('structural_observations').filter(r=>r.feature_type==='contact').length,
        fault_observation_count:selected('fault_intersections').length};
    };
    const holes=t.borehole_collars||[],vertical=holes.filter(r=>r.dip_deg===-90), inclined=holes.filter(r=>r.dip_deg!==-90);
    Object.assign(s,summarizeHoles(holes),{vertical_hole_count:vertical.length,inclined_hole_count:inclined.length,
      surface_sample_count:unique(t.surface_geochemistry||[],'sample_id'),outcrop_count:(t.outcrop_observations||[]).length,
      terrain_observation_count:(t.terrain_observations||[]).length,magnetic_observation_count:(t.magnetic_observations||[]).length,
      gamma_observation_count:(t.gamma_observations||[]).length,geophysical_observation_count:unique([...(t.magnetic_observations||[]),...(t.gamma_observations||[])],'station_id'),
      trench_count:(t.trenches||[]).length,trench_sample_count:unique(t.trench_samples||[],'sample_id'),
      qc_sample_count:unique(t.quality_control||[],'sample_id'),qc_result_count:(t.quality_control||[]).length,
      fault_observation_count:(t.fault_intersections||[]).length,contact_count:(t.structural_observations||[]).filter(r=>r.feature_type==='contact').length});
    s.total_sample_count=s.sample_count+s.surface_sample_count+s.trench_sample_count;
    s.total_assay_count=s.assay_count+(t.surface_geochemistry||[]).length+(t.trench_samples||[]).length;
    const sources=[['vertical_boreholes','Вертикальное бурение',vertical],['inclined_boreholes','Наклонное бурение',inclined]].map(([kind,title,rows])=>({
      source_id:bundle.campaign.campaign_id+':'+kind,kind,title,directory:'sources/'+kind,
      hole_ids:rows.map(r=>r.hole_id), table_names:boreholeTables.filter(k=>Object.hasOwn(bundle.table_fields,k)),summary:summarizeHoles(rows),
    }));
    if(bundle.borehole_sources)bundle.borehole_sources.splice(0,bundle.borehole_sources.length,...sources);
    else bundle.borehole_sources=sources;
    const known=new Set(bundle.rock_catalog.map(r=>r.id));
    for(const table of ['borehole_lithology','trench_intervals','outcrop_observations'])for(const row of t[table]||[]){
      if(!known.has(row.observed_rock_id)&&rocks.has(row.observed_rock_id)){
        const rock=rocks.get(row.observed_rock_id);bundle.rock_catalog.push({id:rock.id,name:rock.name,color:rock.color});known.add(rock.id);
      }
    }
    bundle.geojson??={};
    for(const table of changed)if(pointTables.includes(table)||table==='trenches'){
      const layer=geojsonLayer(bundle,table);bundle.geojson[layer.name]=layer;
    }
  }
  // Validate an entire file before touching the live observation bundle.
  function apply(bundle,payload,{allowedTables,rockReference=[],sourceKind='',filename=''}={}) {
    assert(isObject(payload.tables),'Файл не содержит таблиц');
    const entries=Object.entries(payload.tables);
    assert(entries.length,'Файл не содержит таблиц');
    const additions={},duplicates={};
    for(const [table,rows] of entries){
      assert(Object.hasOwn(keys,table)&&Object.hasOwn(bundle.table_fields,table),'Неизвестная таблица '+table);
      assert(Array.isArray(rows),table+': ожидается массив записей');
      assert(!rows.length||allowedTables?.includes(table),'Таблица '+table+' не относится к выбранному разделу');
      const fields=bundle.table_fields[table],existing=new Map((bundle.tables[table]||[]).map(row=>[recordKey(table,row),row]));
      additions[table]=[];duplicates[table]=0;
      for(let i=0;i<rows.length;i++){
        try{
          const row=normalize(table,rows[i],fields,payload.textValues);
          const key=recordKey(table,row),previous=existing.get(key);
          if(previous){
            assert(rowEqual(previous,row,fields),'Конфликт дубликата '+label(table,row)+': отличаются поля '+fields.filter(f=>canonical(previous[f])!==canonical(row[f])).join(', '));
            duplicates[table]++;continue;
          }
          additions[table].push(row);existing.set(key,row);
        }catch(error){fail(table+', запись '+(i+1)+': '+error.message);}
      }
    }
    const count=Object.values(additions).reduce((n,rows)=>n+rows.length,0);
    const duplicateCount=Object.values(duplicates).reduce((n,v)=>n+v,0);
    assert(count+duplicateCount>0,'В файле нет записей наблюдений');
    const combined={...bundle.tables};
    for(const [table,rows] of Object.entries(additions))combined[table]=[...(combined[table]||[]),...rows];
    const ctx={
      holes:new Map((combined.borehole_collars||[]).map(row=>[row.hole_id,row])),
      trenches:new Map((combined.trenches||[]).map(row=>[row.trench_id,row])),
      structures:new Map((combined.structural_observations||[]).map(row=>[row.observation_id,row])),
      rocks:new Map([...rockReference,...bundle.rock_catalog].map(r=>[r.id,r])),
      analytes:new Map(), samples:sampleRegistry(combined), controls:combined.quality_control||[],
    };
    for(const a of [...(bundle.plan.analytes||[]),...(bundle.plan.methods?.surface_geochemistry?.analytes||[])]){
      if(!ctx.analytes.has(a.analyte))ctx.analytes.set(a.analyte,new Set());
      ctx.analytes.get(a.analyte).add(a.unit);
    }
    if(payload.sourceKind)assert(['vertical_boreholes','inclined_boreholes'].includes(payload.sourceKind),'Неизвестный тип источника бурения');
    const kind=sourceKind||payload.sourceKind;
    if(sourceKind&&payload.sourceKind)assert(sourceKind===payload.sourceKind,'Тип источника файла не совпадает с выбранным источником');
    const intervalTables=['borehole_lithology','trench_intervals','downhole_properties','downhole_gamma','downhole_magnetic','borehole_assays','trench_samples'];
    const intervalGroups={};
    const intervalKey=(table,row)=>JSON.stringify([row.hole_id??row.trench_id,assayTables.includes(table)?row.analyte:null]);
    for(const table of intervalTables)if(additions[table]?.length){
      intervalGroups[table]=new Map();
      for(const row of combined[table]){
        if(row.from_m==null||row.to_m==null)continue;
        const key=intervalKey(table,row),group=intervalGroups[table].get(key)||[];
        group.push(row);intervalGroups[table].set(key,group);
      }
    }
    for(const [table,rows] of Object.entries(additions))for(const row of rows){
      try{
        validate(bundle,table,row,ctx);
        if(kind&&boreholeTables.includes(table)){
          const hole=ctx.holes.get(row.hole_id);
          assert(hole&&(hole.dip_deg===-90)===(kind==='vertical_boreholes'),'Скважина не соответствует выбранному типу бурения');
        }
        // Distinct primary measurements of the same analyte cannot describe
        // overlapping sampling intervals; re-analysis belongs in QA/QC.
        if(intervalGroups[table]&&row.from_m!=null&&row.to_m!=null){
          const group=intervalGroups[table].get(intervalKey(table,row))||[];
          assert(!group.some(other=>other!==row&&Math.min(other.to_m,row.to_m)-Math.max(other.from_m,row.from_m)>1e-6),'Перекрытие интервалов у объекта '+(row.hole_id??row.trench_id));
        }
      }catch(error){fail(table+' ['+label(table,row)+']: '+error.message);}
    }
    if(count){
      const changed=Object.keys(additions).filter(table=>additions[table].length);
      // Prepare all derived metadata on a separate state before committing.
      const prepared={...bundle,tables:combined,summary:{...bundle.summary},
        rock_catalog:[...bundle.rock_catalog],borehole_sources:[...(bundle.borehole_sources||[])],
        geojson:{...(bundle.geojson||{})},import_log:[...(bundle.import_log||[])]};
      refreshMetadata(prepared,changed,ctx.rocks);
      prepared.import_log.push({filename, imported_at:new Date().toISOString(),
        added_count:count,duplicate_count:duplicateCount,tables:Object.fromEntries(changed.map(table=>[table,additions[table].length]))});
      for(const table of changed){
        if(!bundle.tables[table])bundle.tables[table]=[];
        // Preserve references held by the currently displayed maps and filters.
        for(const row of additions[table])bundle.tables[table].push(row);
      }
      Object.assign(bundle.summary,prepared.summary);
      bundle.rock_catalog.splice(0,bundle.rock_catalog.length,...prepared.rock_catalog);
      if(bundle.borehole_sources)bundle.borehole_sources.splice(0,bundle.borehole_sources.length,...prepared.borehole_sources);
      else bundle.borehole_sources=prepared.borehole_sources;
      bundle.geojson=prepared.geojson;bundle.import_log=prepared.import_log;
    }
    return {added:count,duplicates:duplicateCount,byTable:Object.fromEntries(entries.map(([table])=>[table,{added:additions[table].length,duplicates:duplicates[table]}]))};
  }
  return {parseText,parseWorkbook,csvRows,apply,boreholeTables,pointTables,keys,geojsonLayer};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=ObservationImport;
