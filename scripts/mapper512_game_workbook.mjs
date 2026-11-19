// Native-loader ledger, separately scoped from the supported cartridge workbook.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,docs]=process.argv.slice(2);
if(!input||!out||!docs)throw Error('Expected ledger, output directory and docs directory');
const require=createRequire(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/runtime.cjs'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(input,'utf8'));
if(d.launches.length!==2||d.transitions.length!==4||d.timing.length!==6)throw Error('Incomplete native-game matrix');
const w=Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const r=s.getRangeByIndexes(0,0,rows.length+6,headers.length);
 r.format.font={name:'Arial',size:10,color:'#20344A'};r.format.rowHeight=31;r.format.wrapText=true;
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,rows.length+6,1).format.columnWidth=v);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={bold:true,size:16};
 s.getRangeByIndexes(4,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(4,0,1,headers.length).format={fill:'#20344A',font:{bold:true,color:'#FFFFFF'},rowHeight:48,wrapText:true};
 s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;s.freezePanes.freezeRows(5);return s;
}
sheet('Scope','512KiB native loader: experimental qualification',['Item','Evidence','Limit'],[
 ['Status',d.status,'No release or default artifact changes'],
 ['Resource file',`${d.plan.resource_bytes} bytes; ${d.plan.resource_sha256}`,'Disk bytes, not cartridge size'],
 ['Bridge',`${d.plan.bridge_bytes} bytes; ${d.plan.bridge_sha256}`,'Physical30; no extra segment'],
 ['CPU/video',`${d.cycle_ledger.cpu_hz}Hz Z80; ${d.cycle_ledger.refresh_hz}Hz NTSC`,'Presentation FPS is separate from refresh'],
 ['Cycle method',d.cycle_ledger.method,'Self cycles unmeasured; no double counting'],
 ['VBlank',d.cycle_ledger.vblank,d.cycle_ledger.remaining_budget],
 ...d.limits.map((v,i)=>[`Limit${i+1}`,v,'Qualification remains open']),
 ],[23,100,72]).getRange('A6:C16').format.rowHeight=67;
sheet('Routes','Inclusive active-play cycles: mean, tail and maximum',
 ['Mode / round / clock','Version','Active samples','Work mean','Work P95','Work max','Period mean','Period P95','Period max','Presented FPS','Two-refresh work remainder mean'],
 d.timing.flatMap(t=>['control','candidate'].map(k=>{const r=t[k];return[
  `${t.mode} / R${t.round} / ${t.input_clock}`,k,r.active_frames,r.work.mean,r.work.p95,r.work.max,r.period.mean,r.period.p95,r.period.max,3579545/r.period.mean,119472-r.work.mean
 ];})),[30,17,15,19,19,19,20,20,20,20,26]);
sheet('Comparison','No unconditional no-regression verdict',
 ['Mode / round / clock','Mean work delta %','Mean period delta %','Matched native / PSG','Work delta mean','Work delta P95','Work delta max','Slower matched samples','Equal native prefix'],
 d.timing.map(t=>[`${t.mode} / R${t.round} / ${t.input_clock}`,t.mean_work_delta_percent,t.mean_period_delta_percent,t.matching_state_psg_frames,
  t.matching_work_delta.mean,t.matching_work_delta.p95,t.matching_work_delta.max,t.matching_work_slower_samples,t.identical_native_camera_prefix_frames]),[32,21,21,24,21,21,21,24,24]);
sheet('Lifecycle','Native bootstrap and real filesystem transitions',
 ['Path','Round','F10','Graphics','Opening states','Opening tick error','Immutable live bytes checked','Stopped interval cycles'],
 [...d.launches,...d.transitions].map(r=>[r.mode,r.native_round,r.f10?'latched':'off',r.graphics.passed?'pass':'FAIL',r.opening?.frames??'separate launch proof',r.opening?.publication_tick_error_max??'see launch proof',r.immutable_live_bytes_checked??'separate final run',r.stopped_transition_interval_cycles??'not a transition']),[18,16,18,18,25,25,31,29]);
sheet('Seals','Supported formats and canonical workbook remain unchanged',['Path','Bytes','SHA256'],d.artifacts.map(r=>[r.path,r.bytes,r.sha256]),[55,19,100]);
if(d.followup){
 const f=d.followup;
 sheet('Follow-up','Route causality, sound fixtures and natural player turns',['Check','Observed result','Qualification'],[
  ['Status',f.status,'No runtime changes or stable promotion'],
  ['0.24% route',`Equal native/camera/ticks through frame51; candidate publishes one refresh earlier; first native divergence52. Aggregate delta ${f.route.active_mean_interval_delta_percent}%.`,'Later presentation-index routes are different workloads; strict global speed gate remains open'],
  ['Equal prefix work',`${f.route.prefix_mean_work_control} -> ${f.route.prefix_mean_work_candidate} cycles`,'51-frame prefix; no universal speedup claim'],
  ...f.audio.map(r=>[`Audio ${r.mode}`,`${r.matching_psg_samples} identical14-register samples; recorded PCM tone/envelope/retrigger assertions pass`,'Synthetic events/velocities, no listening or natural cue-timing acceptance']),
  ...f.gameplay.map(r=>[`${r.mode}: ${r.players} player(s), F10 ${r.f10?'on':'off'}`,`${r.matching_native_snapshots} matching768-byte native states; ${r.candidate.observation}`,`${r.matching_psg_at_native_tick}/4096 native-index PSG samples match. Physical-clock/audio-boundary differences retained.`]),
  ['Rejected mapper shortcut',`${f.rejected_optimization.abi.cases} ABI cases pass;20 cycles saved per helper call`,'Zero active mean/P95/max work or mean-cadence benefit in measured route. Fully reverted.'],
 ],[34,107,92]).getRange('A6:C14').format.rowHeight=70;
}
await fs.mkdir(out,{recursive:true});
const file=await SpreadsheetFile.exportXlsx(w);
await file.save(path.join(out,'mapper512-native-game.xlsx'));
const target=path.join(docs,'measurements/timing/mapper512-native-game.xlsx');
await fs.copyFile(path.join(out,'mapper512-native-game.xlsx'),target);
const hash=b=>createHash('sha256').update(b).digest('hex'),data=await fs.readFile(target);
const manifestPath=path.join(docs,'measurements/timing/workbooks.json'),m=JSON.parse(await fs.readFile(manifestPath,'utf8'));
m.experimental=(m.experimental||[]).filter(r=>r.path!=='measurements/timing/mapper512-native-game.xlsx');
m.experimental.push({path:'measurements/timing/mapper512-native-game.xlsx',bytes:data.length,sha256:hash(data),
 ledger:'measurements/timing/mapper512-native-game.json',ledger_sha256:hash(await fs.readFile(input)),generator:'scripts/mapper512_game_workbook.mjs',
 generator_sha256:hash(await fs.readFile(new URL(import.meta.url))),reference_rom_sha256:d.plan.reference_rom_sha256,
 bridge_sha256:d.plan.bridge_sha256,resource_sha256:d.plan.resource_sha256,scope:d.status});
await fs.writeFile(manifestPath,JSON.stringify(m,null,2)+'\n');
console.log('Wrote separately scoped native512KiB timing workbook');
