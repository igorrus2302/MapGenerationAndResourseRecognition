/* The browser supplies DOMParser. For the headless Node test, adapt Python's
   standard XML parser to the small DOM subset used by the import engine. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const engine = require('../src/geo_map/observation_import.js');
const root = path.join(__dirname,'../templates/observations/manual');
const workbook = path.join(root,'manual_observations.xlsx');

class XmlNode {
  constructor(raw){this.raw=raw;this.children=raw.children.map(c=>new XmlNode(c));}
  get textContent(){return this.raw.text;}
  getAttribute(name){
    if(name==='r:id')return this.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships','id');
    return this.raw.attributes[name]??null;
  }
  getAttributeNS(ns,name){return this.raw.attributes['{'+ns+'}'+name]??null;}
  getElementsByTagNameNS(_ns,name){
    return this.children.flatMap(child=>[...(child.raw.tag.split('}').at(-1)===name?[child]:[]),...child.getElementsByTagNameNS('*',name)]);
  }
  getElementsByTagName(name){return this.getElementsByTagNameNS('*',name);}
}
global.DOMParser=class{
  parseFromString(source){
    const script=`import sys,json,xml.etree.ElementTree as ET
def convert(node):
 return {'tag':node.tag,'text':''.join(node.itertext()),'attributes':node.attrib,'children':[convert(c) for c in node]}
print(json.dumps(convert(ET.fromstring(sys.stdin.read()))))`;
    const result=spawnSync('python3',['-c',script],{input:source,encoding:'utf8'});
    if(result.status!==0)throw new Error(result.stderr);
    return new XmlNode({tag:'#document',text:'',attributes:{},children:[JSON.parse(result.stdout)]});
  }
};

const fields=Object.fromEntries(fs.readdirSync(root).filter(n=>n.endsWith('.csv')).map(n=>[n.slice(0,-4),fs.readFileSync(path.join(root,n),'utf8').trim().split(',')]));
const table='terrain_observations';
const campaign={campaign_id:'TEST',coordinate_system:'local_cartesian',width_m:500,height_m:500};
const row={campaign_id:'TEST',observation_id:'XLSX-1',x_m:20,y_m:30,surface_elevation_m:12.5,elevation_uncertainty_m:.2,slope_deg:4,local_relief_m:null,terrain_type:'flat',observation_method:'survey',survey_date:'2026-11-25'};
const newBundle=()=>({campaign,plan:{analytes:[],methods:{}},table_fields:fields,tables:Object.fromEntries(Object.keys(fields).map(k=>[k,[]])),summary:{},rock_catalog:[],geojson:{},borehole_sources:[]});
function filledWorkbook(compression,formula=false){
  const script=`import io,json,sys,zipfile,xml.etree.ElementTree as ET
ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
source=sys.argv[1]; compression=int(sys.argv[2]); formula=sys.argv[3]=='true'
values=json.loads(sys.stdin.read())
with zipfile.ZipFile(source) as old:
 sheets=ET.fromstring(old.read('xl/workbook.xml')).find('{'+ns+'}sheets')
 i=next(i for i, sheet in enumerate(sheets,1) if sheet.attrib['name']=='terrain_observations')
 name=f'xl/worksheets/sheet{i}.xml'
 root=ET.fromstring(old.read(name)); data=root.find('{'+ns+'}sheetData')
 row=ET.SubElement(data,'{'+ns+'}row',{'r':'2'})
 header=list(data[0]); fields=[''.join(x.itertext()) for x in header]
 for col, field in enumerate(fields):
  value=values[field]
  if value is None: continue
  cell=ET.SubElement(row,'{'+ns+'}c',{'r':chr(65+col)+'2'})
  if formula and field=='x_m':
   ET.SubElement(cell,'{'+ns+'}f').text='10+10'
  elif isinstance(value,str):
   cell.set('t','inlineStr'); ET.SubElement(ET.SubElement(cell,'{'+ns+'}is'),'{'+ns+'}t').text=value
  else: ET.SubElement(cell,'{'+ns+'}v').text=str(value)
 output=io.BytesIO()
 with zipfile.ZipFile(output,'w',compression) as new:
  for part in old.namelist():new.writestr(part,ET.tostring(root) if part==name else old.read(part))
 sys.stdout.buffer.write(output.getvalue())`;
  const result=spawnSync('python3',['-c',script,workbook,String(compression),String(formula)],{input:JSON.stringify(row),maxBuffer:2e6});
  assert.equal(result.status,0,result.stderr?.toString());
  return {arrayBuffer:async()=>result.stdout.buffer.slice(result.stdout.byteOffset,result.stdout.byteOffset+result.stdout.byteLength)};
}
(async()=>{
  for(const mode of [0,8]){
    const bundle=newBundle();
    const payload=await engine.parseWorkbook(filledWorkbook(mode),bundle,[table]);
    const result=engine.apply(bundle,payload,{allowedTables:[table]});
    assert.equal(result.added,1);assert.deepEqual(bundle.tables[table][0],row);
  }
  await assert.rejects(()=>engine.parseWorkbook(filledWorkbook(0,true),newBundle(),[table]),/формулы/);
  console.log('XLSX stored/deflated workbook, typed fields and rejection of formulas: OK');
})().catch(error=>{console.error(error);process.exitCode=1});
