const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const engine = require('../src/geo_map/observation_import.js');

const templateDir = path.join(__dirname,'../templates/observations/manual');
const fields = Object.fromEntries(fs.readdirSync(templateDir).filter(n=>n.endsWith('.csv')).map(n=>[n.slice(0,-4),fs.readFileSync(path.join(templateDir,n),'utf8').trim().split(',')]));
const campaign={campaign_id:'TEST',coordinate_system:'local_cartesian',width_m:500,height_m:500,date:'2026-11-25'};
function fixture(){
  return {campaign:{...campaign},plan:{analytes:[{analyte:'Cu',unit:'% Cu'},{analyte:'Au',unit:'g/t Au'}],methods:{}},
    table_fields:fields,tables:Object.fromEntries(Object.keys(fields).map(k=>[k,[]])),
    summary:{},rock_catalog:[{id:'granite',name:'Гранит',color:'#aaa'}],geojson:{},borehole_sources:[]};
}
const row=(table,values)=>({...Object.fromEntries(fields[table].map(k=>[k,null])),campaign_id:'TEST',...values});
const metadata={analysis_method:'laboratory',laboratory:'LAB',certificate_id:'CERT',qc_type:'primary',qc_flag:'not_checked',result_value:.5,unit:'% Cu',analyte:'Cu',detection_limit:.01};
const survey={x_m:40,y_m:40,surface_elevation_m:12,observation_method:'survey',survey_date:'2026-11-25',position_uncertainty_m:1};
const borehole=row('borehole_collars',{hole_id:'BH-X',x_m:100,y_m:100,collar_elevation_m:0,total_depth_m:50,azimuth_deg:0,dip_deg:-90,coordinate_system:'local_cartesian',position_uncertainty_m:1,drilling_method:'core',start_date:'2026-11-24',end_date:'2026-11-25',hole_status:'completed'});
const assay=row('borehole_assays',{...metadata,sample_id:'S-X',hole_id:'BH-X',from_m:0,to_m:5});
const terrain=row('terrain_observations',{observation_id:'T-X',x_m:50,y_m:50,surface_elevation_m:4,elevation_uncertainty_m:.2,slope_deg:2,local_relief_m:0,terrain_type:'flat',observation_method:'survey',survey_date:'2026-11-25'});
const magnetic=row('magnetic_observations',{...survey,observation_id:'M-X',station_id:'ST-X',magnetic_anomaly_nt:-3,magnetic_sigma_nt:.5});
const gamma=row('gamma_observations',{...survey,observation_id:'G-X',station_id:'ST-X',gamma_count_rate_cps:20,gamma_sigma_cps:.5});
const outcrop=row('outcrop_observations',{...survey,observation_id:'O-X',observed_rock_id:'granite',observed_rock_name:'Гранит'});
const lithology=row('borehole_lithology',{hole_id:'BH-X',interval_id:'L-X',from_m:0,to_m:50,observed_rock_id:'granite',observed_rock_name:'Гранит',confidence:'high',observer:'geologist',logged_date:'2026-11-25'});
const properties=row('downhole_properties',{hole_id:'BH-X',measurement_id:'P-X',from_m:0,to_m:5,density_g_cm3:2.7,porosity_percent:2,measurement_method:'core',qc_flag:'not_checked'});
const downGamma=row('downhole_gamma',{hole_id:'BH-X',measurement_id:'DG-X',from_m:0,to_m:1,depth_m:.5,gamma_count_rate_cps:10,gamma_sigma_cps:.3,counting_time_s:60,measurement_method:'logger',logged_date:'2026-11-25'});
const downMagnetic=row('downhole_magnetic',{hole_id:'BH-X',measurement_id:'DM-X',from_m:0,to_m:1,depth_m:.5,magnetic_susceptibility_si:-0.00002,magnetic_sigma_si:.00005,measurement_method:'logger',logged_date:'2026-11-25'});
const structure=row('structural_observations',{observation_id:'F-X',hole_id:'BH-X',depth_m:4,feature_type:'fault',strike_deg:30,dip_deg:45,dip_direction_deg:120,confidence:'high',observation_method:'core'});
const fault=row('fault_intersections',{observation_id:'F-X',hole_id:'BH-X',from_m:3,to_m:5,observation_method:'core',confidence:'high'});
const trench=row('trenches',{trench_id:'TR-X',start_x_m:100,start_y_m:200,end_x_m:120,end_y_m:200,depth_m:2,width_m:1,surveyed_length_m:20,position_uncertainty_m:1,trench_status:'completed',survey_date:'2026-11-25'});
const trenchLog=row('trench_intervals',{trench_id:'TR-X',interval_id:'TL-X',from_m:0,to_m:20,observed_rock_id:'granite',observed_rock_name:'Гранит',sample_material:'rock',confidence:'high'});
const trenchSample=row('trench_samples',{...metadata,trench_id:'TR-X',sample_id:'TS-X',from_m:0,to_m:5,sampling_depth_from_m:1.8,sampling_depth_to_m:2,sample_material:'rock',sampling_method:'channel'});
const surface=row('surface_geochemistry',{...metadata,sample_id:'SS-X',x_m:20,y_m:20,sample_date:'2026-11-25',sample_material:'soil',sampling_depth_from_m:.2,sampling_depth_to_m:.4,sampling_method:'soil_sample',position_uncertainty_m:1});
const qc=row('quality_control',{analyte:'Cu',unit:'% Cu',result_value:.5,detection_limit:.01,control_id:'QC-X',sample_id:'QCS-X',parent_sample_id:'S-X',sample_source:'borehole',hole_id:'BH-X',qc_type:'duplicate',acceptance_limit:20,acceptance_unit:'%',qc_flag:'pass'});
const all={
  quality_control:[qc],fault_intersections:[fault],trench_samples:[trenchSample],borehole_assays:[assay,{...assay,analyte:'Au',unit:'g/t Au'}],
  borehole_collars:[borehole],borehole_lithology:[lithology],downhole_properties:[properties],downhole_gamma:[downGamma],downhole_magnetic:[downMagnetic],structural_observations:[structure],
  trenches:[trench],trench_intervals:[trenchLog],surface_geochemistry:[surface],terrain_observations:[terrain],outcrop_observations:[outcrop],magnetic_observations:[magnetic],gamma_observations:[gamma],
};
const bundle=fixture(), allowed=Object.keys(fields);
const importRows=(target,tables,options={})=>engine.apply(target,{tables,textValues:false},{allowedTables:allowed,filename:'example.json',...options});
const parsed=engine.parseText('all.json',JSON.stringify({campaign,tables:all}),null,bundle);
const result=engine.apply(bundle,parsed,{allowedTables:allowed,filename:'all.json'});
assert.equal(result.added,18);
assert.equal(bundle.summary.hole_count,1);
assert.equal(bundle.summary.magnetic_log_count,1);
assert.equal(bundle.borehole_sources[0].summary.magnetic_log_count,1);
assert.equal(bundle.summary.total_sample_count,3);
assert.equal(bundle.summary.geophysical_observation_count,1);
assert.equal(bundle.borehole_sources[0].hole_ids[0],'BH-X');
assert.equal(bundle.geojson.trench_paths.features[0].id,'TR-X');
assert.equal(bundle.geojson.surface_geochemistry.features[0].id,'SS-X-Cu');
assert.equal(bundle.import_log.length,1);
const before=JSON.stringify(bundle);
const dup=importRows(bundle,all,{filename:'renamed.json'});
assert.equal(dup.added,0);
assert.equal(dup.duplicates,18);
assert.equal(JSON.stringify(bundle),before);
function reject(tables,match,options={}){
  const original=JSON.stringify(bundle);
  assert.throws(()=>importRows(bundle,tables,options),match);
  assert.equal(JSON.stringify(bundle),original,'rejected transaction must leave all data unchanged');
}
reject({terrain_observations:[{...terrain,surface_elevation_m:8}]},/Конфликт дубликата.*surface_elevation_m/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',x_m:80},{...terrain,observation_id:'BAD',x_m:10000}]},/Координаты/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',terrain_type:'mountain'}]},/terrain_type/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',survey_date:'2026-02-30'}]},/дата/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',campaign_id:'OTHER'}]},/campaign_id/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',x_m:'40'}]},/конечное число/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',secret:'hidden'}]},/лишние/);
reject({terrain_observations:[{...terrain,observation_id:'T-NEW',surface_elevation_m:null}]},/обязательное поле/);
reject({borehole_assays:[{...assay,sample_id:'NEW',hole_id:'UNKNOWN'}]},/Неизвестная скважина/);
reject({borehole_assays:[{...assay,sample_id:'NEW',to_m:60}]},/интервал/);
reject({borehole_assays:[{...assay,sample_id:'NEW',unit:'kg'}]},/единица/);
reject({borehole_assays:[{...assay,analyte:'Ag',unit:'g/t Ag',from_m:5,to_m:10}]},/Проба S-X.*разные/);
reject({borehole_lithology:[{...lithology,interval_id:'NEW',from_m:10,to_m:20}]},/Перекрытие/);
reject({fault_intersections:[{...fault,observation_id:'UNKNOWN'}]},/ссылаться/);
reject({quality_control:[{...qc,control_id:'NEW',sample_id:'NEW',parent_sample_id:'UNKNOWN'}]},/Исходная проба/);
reject({borehole_collars:[{...borehole,hole_id:'NEW',dip_deg:-90}]},/типу бурения/,{sourceKind:'inclined_boreholes'});
reject({magnetic_observations:[{...magnetic,observation_id:'NEW'}]},/не относится/,{allowedTables:['terrain_observations']});
reject({downhole_magnetic:[{...downMagnetic,magnetic_susceptibility_si:.005}]},/Конфликт дубликата/);
reject({downhole_magnetic:[{...downMagnetic,measurement_id:'NEW',from_m:1,to_m:2,depth_m:1.1}]},/середина интервала/);
reject({downhole_magnetic:[{...downMagnetic,measurement_id:'NEW',magnetic_sigma_si:-1}]},/отрицательным/);
reject({downhole_magnetic:[{...downMagnetic,measurement_id:'NEW'}]},/Перекрытие/);
reject({downhole_magnetic:[{...downMagnetic,measurement_id:'NEW',hole_id:'UNKNOWN'}]},/Неизвестная скважина/);
reject({downhole_magnetic:[{...downMagnetic,measurement_id:'NEW',from_m:49,to_m:51,depth_m:50}]},/интервал/);
// CSV quoting, different order, decimal semicolon, BOM and duplicate within the file.
const csvField=fields.terrain_observations;
const csvRow={...terrain,observation_id:'T-CSV',observation_method:'метод, с "кавычками"\nи переносом'};
const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
const csv='\ufeff'+csvField.map(quote).join(',')+'\r\n'+csvField.map(k=>quote(csvRow[k])).join(',')+'\r\n';
const parsedCsv=engine.parseText('terrain.csv',csv,'terrain_observations',bundle);
const csvResult=engine.apply(bundle,parsedCsv,{allowedTables:['terrain_observations']});
assert.equal(csvResult.added,1);
assert.equal(bundle.tables.terrain_observations.at(-1).observation_method,csvRow.observation_method);
assert.throws(()=>engine.parseText('wrong.csv','campaign_id,x_m\nTEST,1','terrain_observations',bundle),/не соответствует/);
assert.throws(()=>engine.parseText('bad.csv','"broken','terrain_observations',bundle),/незакрытая/);
const layer=engine.geojsonLayer(bundle,'magnetic_observations');
assert.equal(engine.apply(bundle,engine.parseText('magnetic.geojson',JSON.stringify(layer),'magnetic_observations',bundle),{allowedTables:['magnetic_observations']}).duplicates,1);
assert.throws(()=>engine.parseText('wrong.geojson',JSON.stringify(layer),'gamma_observations',bundle),/не соответствует/);
const magneticCsvFields=fields.downhole_magnetic;
const magneticCsvRow={...downMagnetic,measurement_id:'DM-CSV',from_m:1,to_m:2,depth_m:1.5,magnetic_susceptibility_si:.002};
const magneticCsv=magneticCsvFields.join(',')+'\n'+magneticCsvFields.map(k=>quote(magneticCsvRow[k])).join(',')+'\n';
assert.equal(engine.apply(bundle,engine.parseText('magnetic_log.csv',magneticCsv,'downhole_magnetic',bundle),{allowedTables:['downhole_magnetic']}).added,1);
assert.equal(bundle.summary.magnetic_log_count,2);
console.log('Import engine: all 17 schemas, CSV/GeoJSON/JSON, duplicate/conflict, references, atomicity and metadata OK');
