import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,docs]=process.argv.slice(2);
if(!input||!out||!docs)throw Error('Usage: turbo_workbook.mjs ledger.json output-directory docs-directory');
let artifact;
try{artifact=await import('@oai/artifact-tool');}
catch(e){
 if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;
 const require=createRequire(path.join(process.env.ARTIFACT_TOOL_NODE_ROOT||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'),'runtime.cjs'));
 artifact=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
}
const d=JSON.parse(await fs.readFile(input,'utf8'));
if(d.turbo_matrix.length!==(d.asset_update?1:d.auto_policy?33:66)||d.turbo_matrix.some(r=>!r.passed))throw Error('Incomplete CPU matrix');
const hash=b=>createHash('sha256').update(b).digest('hex');
const generatorHash=hash(await fs.readFile(new URL(import.meta.url)));
const w=artifact.Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const count=Math.max(rows.length+6,24);
 const all=s.getRangeByIndexes(0,0,count,headers.length);
 all.format.font={name:'Arial',size:10,color:'#20344A'};all.format.rowHeight=24;
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,count,1).format.columnWidth=v);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#20344A'};
 s.getRangeByIndexes(4,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(4,0,1,headers.length).format={fill:'#20344A',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:42};
 if(rows.length)s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;
 s.freezePanes.freezeRows(5);return s;
}
const hz=d.cpu_hz;
const summary=sheet('Summary',d.asset_update?'Title asset update: current-ROM validation':d.auto_policy?'Issue39: automatic mapper and CPU selection':'Issue39: software-controlled CPU scopes', ['Measure','Value','Unit','Evidence'],[
 ['Primary ROM',d.rom_sha256,'SHA256',d.auto_policy?'MAPPER=auto TURBO=1; minimum64KiB, compact HUD':'TURBO=1,64KiB, compact HUD; opt-in candidate'],
 ['Cartridge bytes',d.rom_bytes,'bytes','2MiB hard limit; no image growth'],
 ['Machine',d.machine,'openMSX21.0','Physical hardware unavailable'],
 ['Native population',d.enemy_count,'enemies','Keyboard coin/start/F5; no population override'],
 ['Active presentations',d.active_frames,'frames','Both endpoints active; menus/death/bonus excluded'],
 ['Presentation rate',d.presented_fps,'FPS','Physical refresh is listed separately'],
 ['Mean work',d.work.mean/hz*1000,'ms','Includes CPU switching; excludes synchronization waits'],
 ['P95 work',d.work.p95/hz*1000,'ms','Elapsed time, including hardware wait states'],
 ['Maximum work',d.work.max/hz*1000,'ms','Short directional workload'],
 ['Late presentations',d.late_frames,'frames','More than two physical refreshes'],
 ['Physical refresh',d.calibration.refresh_hz,'Hz','Native VDP endpoints checked'],
 ['Two-refresh target',d.calibration.two_refresh_fps,'FPS','Approximately30FPS target; no blanket acceptance'],
 ['VBlank reserve',5000,'reference cycles','Unverified planning assumption'],
 [d.auto_policy?'Automatic profile cases':'Paired profile cases',d.turbo_matrix.length,'runs',d.asset_update?'Current logo ROM: WSX64 only; earlier full matrix retains its original ROM hash':d.auto_policy?'One ROM; five targets plus Sony64 control; actual RAM/backend observed':'All five targets; stock Sony64 control;11 observed base-CPU checks'],
 ['Session regression cases',d.regression_matrix.length,'checks','Graphics, HUD, cars, radar, flags, challenge, two-player, attract, smoke'],
 ['Long/component cases',d.long_matrix.length,'checks','16000-refresh steering, smoke, audio, boot, speed, clipping'],
 ['CPU timing units','Elapsed guest time','s / ms','Source *_cycles = seconds x3579545 reference Hz; never R800 instruction cycles'],
 ['Source base',d.working_tree_base,'Git SHA','Authored source hashes are in the ledger'],
 ['User acceptance','Pending','audio / perception','No physical-machine claim; no issue closure'],
 ],[29,69,20,91]);
summary.getRange('A6:D24').format.wrapText=true;summary.getRange('A6:D24').format.rowHeight=34;
summary.getRange('B11:B14').setNumberFormat('0.000');summary.getRange('B16:B17').setNumberFormat('0.000');
const matrixSheet=sheet('CPU matrix',d.auto_policy?'One ROM: observed mapper capacity and CPU backend':'Same-machine base / factory-turbo workloads',
 ['Machine','RAM KiB','Enemies','CPU policy','Mean ms','P95 ms','Max ms','FPS','Late','Active','ROM SHA256'],
 d.turbo_matrix.map(r=>[r.machine,d.auto_policy?r.mapper_kib:r.ram_profile_kib,r.enemy_count,r.turbo?(r.actual_backend_kind===2?'R800 scopes':r.actual_backend_kind===1?'Z80 5.37MHz scopes':'Z80 fallback'):'Base Z80',...['mean','p95','max'].map(k=>r.work[k]/hz*1000),r.presented_fps,r.late_frames,r.active_frames,r.rom_sha256]),
 [31,12,12,21,15,15,15,14,12,12,69]);
matrixSheet.getRange(`E6:H${d.turbo_matrix.length+5}`).setNumberFormat('0.000');
const routineSheet=sheet('Routines','Primary ROM: inclusive and self elapsed time',
 ['Routine','Calls/frame','Incl mean ms/frame','Incl P95 ms/frame','Incl max ms/frame','Self mean ms/frame','Self P95 ms/frame','Self max ms/frame'],
 d.routines.filter(r=>r.mean!==null).map(r=>[r.name,r.calls_per_frame,...['mean','p95','max'].map(k=>r.frame_cycles[k]/hz*1000),...['mean','p95','max'].map(k=>r.self_frame_cycles[k]/hz*1000)]),
 [45,15,20,20,20,20,20,20]);
routineSheet.getRange(`B6:H${d.routines.filter(r=>r.mean!==null).length+5}`).setNumberFormat('0.000');
const frames=sheet('Frames','Primary ROM: work, waits and remaining budget',
 ['Frame','Refreshes','Interval ms','Work ms','Ready margin ms','Logic ms','Render ms','Wait ms','Commit ms','Untracked ms'],
 d.frames.map(f=>[f.frame,f.refreshes,...['interval_cycles','work_cycles','ready_margin','logic_cycles','render_cycles','wait_cycles','commit_cycles','untracked_cycles'].map(k=>f[k]/hz*1000)]),
 [12,13,18,18,20,18,18,18,18,18]);
const end=d.frames.length+5;
frames.getRange(`C6:J${end}`).setNumberFormat('0.000');
summary.getRange('A26:D27').values=[['Frame mean work',null,'ms','Recalculated from recorded frames'],['Frame minimum readiness',null,'ms','Worst remaining drawing budget']];
summary.getRange('B26:B27').formulas=[[`=AVERAGE('Frames'!D6:D${end})`],[`=MIN('Frames'!E6:E${end})`]];
summary.getRange('B26:B27').setNumberFormat('0.000');
sheet('Factory probe','Synthetic instruction qualification; BIOS Page0 visible',
 ['Machine','Mode','Location','CPU','Z80 Hz','Time ms','Controller'],
 d.factory_cpu_probe.results.flatMap(r=>r.samples.map(s=>[r.machine,Number(s.mode),s.location,s.cpu,Number(s.z80_hz),Number(s.seconds)*1000,Number(s.controller)])),
 [32,12,15,15,19,20,18]);
sheet('Verification','Emulator checks; fixtures and natural input are distinct',
 ['Machine','RAM KiB','Turbo','Case','Passed','ROM SHA256','Evidence log'],
 [...d.regression_matrix,...d.long_matrix,...d.base_mode_matrix,...(d.boot_matrix||[]),...(d.capacity_matrix||[])].map(r=>[r.machine,r.mapper_kib??r.ram_profile_kib,r.turbo,r.case,r.passed,r.rom_sha256,r.log]),
 [31,12,12,25,12,69,100]);
if(d.component_checks.length)sheet('Components','Additional controlled safety checks; base Z80 outside turbo scopes',
 ['Component','Machine','RAM KiB','Cases','Passed','Timing scope','Evidence'],
 d.component_checks.map(r=>[r.kind,r.machine,r.ram_profile_kib,r.cases,r.passed,'Inclusive component costs in source ledger; self costs not separated',r.source]),
 [22,33,12,15,12,87,100]);
if(d.auto_policy){
 sheet('Mapper detection','Reversible mapper probe and first-screen pixel verification',
  ['Machine','Reference request KiB','Observed KiB','Cache tier KiB','Turbo backend','Bytes restored','Passed','Evidence'],
  [...d.boot_matrix,...d.capacity_matrix].map(r=>[r.machine,r.ram_profile_kib,r.mapper_kib,r.selected_profile_kib,r.actual_backend_kind,r.probe_restored,r.passed,r.log]),
  [32,23,19,19,19,20,12,100]);
 if(d.mapper_comparisons.length){const cache=sheet('Mapper comparison','Same-ROM workloads:64KiB versus128KiB cache selection',
  ['Machine','Enemies','Low RAM KiB','High RAM KiB','Low FPS','High FPS','Mean work reduction %','P95 reduction %','Max reduction %'],
  d.mapper_comparisons.map(r=>[r.machine,r.enemies,r.low_mapper_kib,r.high_mapper_kib,r.low_fps,r.high_fps,r.mean_work_reduction_percent,r.p95_work_reduction_percent,r.max_work_reduction_percent]),
  [32,13,19,19,17,17,27,24,24]);
 cache.getRange(`E6:I${d.mapper_comparisons.length+5}`).setNumberFormat('0.000');
 }
}
w.recalculate();await fs.mkdir(out,{recursive:true});
const errors=await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30}});
await fs.writeFile(path.join(out,'workbook-errors.ndjson'),errors.ndjson);
if(/"kind":"match"/.test(errors.ndjson))throw Error('Workbook formula errors');
for(const [name,range] of [['Summary','A1:D27'],['CPU matrix','A1:J18'],['Routines','A1:H18']]){
 const png=await w.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,name.toLowerCase().replaceAll(' ','-')+'.png'),new Uint8Array(await png.arrayBuffer()));
}
const file=await artifact.SpreadsheetFile.exportXlsx(w);await file.save(path.join(out,'cycle-budget.xlsx'));
const timing=path.join(docs,'measurements/timing'),manifestPath=path.join(timing,'workbooks.json');
const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
const target=path.join(docs,'cycle-budget.xlsx'),previous=await fs.readFile(target),data=await fs.readFile(path.join(out,'cycle-budget.xlsx'));
const ledger=await fs.readFile(input),previousHash=hash(previous);
if(previousHash!==hash(data)&&!manifest.historical.some(r=>r.sha256===previousHash)){
 const relative=`measurements/timing/archive/retained-${previousHash.slice(0,16)}/cycle-budget.xlsx`;
 await fs.mkdir(path.dirname(path.join(docs,relative)),{recursive:true});await fs.writeFile(path.join(docs,relative),previous);
 const retained={source:'Previous docs/cycle-budget.xlsx',path:relative,bytes:previous.length,sha256:previousHash,scope:'Historical workbook; retain its original ROM hash and workload.'};
 if(manifest.current?.sha256===previousHash&&manifest.current.ledger){
  const prior=await fs.readFile(path.join(docs,manifest.current.ledger));
  if(hash(prior)!==manifest.current.ledger_sha256)throw Error('Previous workbook ledger hash changed');
  retained.ledger=path.posix.join(path.posix.dirname(relative),'cycle-ledger.json');retained.ledger_sha256=hash(prior);retained.rom_sha256=manifest.current.rom_sha256;
  await fs.writeFile(path.join(docs,retained.ledger),prior);
 }
 manifest.historical.push(retained);
}
await fs.writeFile(path.join(timing,'cycle-ledger.json'),ledger);
manifest.current={path:'cycle-budget.xlsx',bytes:data.length,sha256:hash(data),rom_sha256:d.rom_sha256,rom_bytes:d.rom_bytes,
 ledger:'measurements/timing/cycle-ledger.json',ledger_sha256:hash(ledger),generator:'src/toolchain/screen4/turbo_workbook.mjs',generator_sha256:generatorHash,scope:d.workload+(d.auto_policy?'; one automatic mapper/CPU ROM, observed RAM and selected cache tier.':'; opt-in factory CPU scopes and paired matrix.')};
await fs.writeFile(target+'.tmp',data);await fs.rename(target+'.tmp',target);
await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log(target);
