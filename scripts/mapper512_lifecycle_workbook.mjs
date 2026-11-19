// Separate exact-artifact lifecycle ledger; canonical cartridge workbook is sealed.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,docs]=process.argv.slice(2);
if(!input||!out||!docs)throw Error('Expected ledger, output and docs directories');
const require=createRequire(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/runtime.cjs'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const raw=await fs.readFile(input),d=JSON.parse(raw),hash=b=>createHash('sha256').update(b).digest('hex');
if(d.matrix.length!==23||d.performance.length!==6||d.pcm.length!==2)throw Error('Incomplete matrix');
const w=Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const area=s.getRangeByIndexes(0,0,rows.length+6,headers.length);
 area.format.font={name:'Arial',size:10,color:'#20344A'};area.format.rowHeight=34;area.format.wrapText=true;
 widths.forEach((n,i)=>s.getRangeByIndexes(0,i,rows.length+6,1).format.columnWidth=n);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={bold:true,size:16};
 const head=s.getRangeByIndexes(4,0,1,headers.length);head.values=[headers];
 head.format={fill:'#20344A',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:46};
 s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;s.freezePanes.freezeRows(5);return s;
}
sheet('Scope','512KiB lifecycle and diagnostic ROM',['Item','Observed result','Limit'],[
 ['Status',d.status,'No release or hardware acceptance'],
 ['Test ROM',d.carrier.rom_sha256,'512KiB ASCII8 carrier,512KiB main mapper,128KiB VRAM; embedded cold transport'],
 ['DAT',d.candidate.resource_sha256,`${d.candidate.resource_bytes} bytes; real DOS1/BASIC separate from carrier`],
 ['Bridge',d.candidate.bridge_sha256,`${d.candidate.bridge_bytes} bytes; no extra segment`],
 ['Existing symbols',d.existing_symbol_values_preserved,'All values retained; new cold helper in resident padding'],
 ['Cycle method',d.cycle_ledger.method,'Inclusive parents and children overlap'],
 ['VBlank',d.cycle_ledger.vblank,'No new measured usable VBlank limit'],
 ...d.limits.map((v,i)=>[`Limit${i+1}`,v,'See report']),
 ],[28,107,87]).getRange('A6:C17').format.rowHeight=78;
sheet('Lifecycle','23 actual boots and game lifecycle cases',
 ['Mode','Scenario','Round','F10','Reset','Graphics snapshots','Opening states','Settlement seconds','Cold + UI to next play seconds','Deaths','F10 after reset','Observer SHA256'],
 d.matrix.map(r=>{const e=Object.fromEntries(r.lifecycle.map(v=>[v.event,v]));return[
  r.mode,r.scenario,r.native_round,r.f10?'on':'off',r.reset_check?'yes':'no',r.graphics_snapshots,r.opening_states,
  e.fuel_bonus?e.fuel_bonus.seconds-e.settlement.seconds:0,
  e.next_stage?e.next_stage.seconds-e.native_next_round.seconds:0,
  r.lifecycle.filter(v=>v.event==='death').length,e.reset_post_play?.f10??'',r.verification_script_sha256];}),
 [17,23,13,13,13,23,23,25,34,15,24,78]);
sheet('Work','Six scoped active-game routes; raw aggregates, not matched speedups',
 ['Mode','Round','Enemies','Active /360','Mean work','P95 work','Max work','Mean period','P95 period','Max period','Presented FPS','Mean budget remainder'],
 d.performance.map(r=>[r.mode,r.native_round,r.enemies.join('/'),r.active_frames,r.work.mean,r.work.p95,r.work.max,
 r.period.mean,r.period.p95,r.period.max,r.presented_fps,r.work_budget_remaining.mean]),
 [16,14,16,21,22,22,22,23,23,23,23,29]);
sheet('Ownership','Inclusive work, worker and IRQ overlap remain separate',
 ['Mode / round','Audio calls / present mean','Audio inclusive mean','Audio excluding IRQ mean','IRQ inclusive mean','Work excluding audio / IRQ mean','Publish tail + waits mean','Tail / wait interpretation'],
 d.performance.map(r=>[`${r.mode} /${r.native_round}`,r.audio_calls_per_present.mean,r.audio_inclusive.mean,r.audio_without_irq.mean,
 r.irq_inclusive.mean,r.work_without_audio_irq.mean,r.publish_tail_and_wait.mean,'Includes commit and other publication tail; not pure synchronization wait']),
 [23,29,29,31,28,39,31,64]);
sheet('Historical deltas','Unchanged and slower cases remain visible; no matched-trajectory verdict',
 ['Mode','Round','Delta mean work','Delta P95 work','Delta max work','Interpretation'],
 d.performance.map(r=>[r.mode,r.native_round,r.historical_work_delta.mean,r.historical_work_delta.p95,r.historical_work_delta.max,
 'Current minus previous exact-artifact aggregate. Different clock alignment / trajectories may differ. Earlier0.24percent route remains open.']),
 [20,18,25,25,25,110]);
sheet('Seals','Supported files remain byte-identical',['Path','Bytes','SHA256'],d.seals.map(r=>[r.path,r.bytes,r.sha256]),[75,23,100]);
await fs.mkdir(out,{recursive:true});const name='mapper512-lifecycle.xlsx';
const book=await SpreadsheetFile.exportXlsx(w);await book.save(path.join(out,name));
const target=path.join(docs,'measurements/timing',name);await fs.copyFile(path.join(out,name),target);
const data=await fs.readFile(target),mp=path.join(docs,'measurements/timing/workbooks.json'),m=JSON.parse(await fs.readFile(mp));
m.experimental??=[];m.experimental=m.experimental.filter(r=>r.path!==`measurements/timing/${name}`);
m.experimental.push({path:`measurements/timing/${name}`,bytes:data.length,sha256:hash(data),ledger:'measurements/timing/mapper512-lifecycle.json',ledger_sha256:hash(raw),
 generator:'scripts/mapper512_lifecycle_workbook.mjs',generator_sha256:hash(await fs.readFile(new URL(import.meta.url))),reference_rom_sha256:d.seals[0].sha256,
 bridge_sha256:d.candidate.bridge_sha256,resource_sha256:d.candidate.resource_sha256,scope:d.status});
await fs.writeFile(mp,JSON.stringify(m,null,2)+'\n');console.log('Wrote separately sealed512KiB lifecycle workbook');
