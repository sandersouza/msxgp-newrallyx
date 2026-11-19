// Measured512KiB continuation only; never replace canonical cartridge timing.
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
if(d.performance.length!==6||d.natural_audio.length!==3||d.pcm.length!==2)throw Error('Incomplete matrix');
const w=Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const r=s.getRangeByIndexes(0,0,rows.length+6,headers.length);r.format.font={name:'Arial',size:10,color:'#20344A'};r.format.rowHeight=32;r.format.wrapText=true;
 widths.forEach((n,i)=>s.getRangeByIndexes(0,i,rows.length+6,1).format.columnWidth=n);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={bold:true,size:16};
 s.getRangeByIndexes(4,0,1,headers.length).values=[headers];s.getRangeByIndexes(4,0,1,headers.length).format={fill:'#20344A',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:46};
 s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;s.freezePanes.freezeRows(5);return s;
}
sheet('Scope','512KiB natural sound and phase-cache validation',['Item','Observed result','Limit'],[
 ['Status',d.status,'No stable/hardware/listening promotion'],
 ['Current DAT',d.candidate.resource_sha256,`${d.candidate.resource_bytes} bytes; disk-file size, not a512KiB cartridge`],
 ['Current bridge',d.candidate.bridge_sha256,`${d.candidate.bridge_bytes} bytes; no extra mapper segment`],
 ['Immutable owners','All four hot images and all symbol values match baseline','Changed Page0 phase exit only; padding after RET is unreachable'],
 ['Clock basis',`${d.cycle_ledger.cpu_hz}Hz Z80 / ${d.cycle_ledger.refresh_hz}Hz refresh`,'Presentation rate is distinct'],
 ['Cycle method',d.cycle_ledger.method,'Phase child is not added to parent work'],
 ['VBlank',d.cycle_ledger.vblank,'No new measured hardware margin'],
 ...d.limits.map((r,i)=>[`Limit${i+1}`,r,'See local report']),
 ],[28,103,81]).getRange('A6:C15').format.rowHeight=66;
sheet('Performance','Six matched routes: current and exact pre-change512KiB package',
 ['Mode / round','Version','Active frames','Mean work','P95 work','Max work','Mean period','P95 period','Max period','Presented FPS','Mean work budget remainder'],
 d.performance.flatMap(r=>['control','candidate'].map(k=>{const v=r[k];return[`${r.mode} / R${r.round}`,k,v.active_frames,v.work.mean,v.work.p95,v.work.max,v.period.mean,v.period.p95,v.period.max,3579545/v.period.mean,119472-v.work.mean];})),[22,17,18,19,19,19,21,21,21,21,29]);
sheet('Phase','Inclusive phase selector: identical cache context, no IRQ overlap',['Metric','Value','Meaning'],[
 ['Input-context pairs',d.phase.input_context_pairs,'Target/native/front/keys/lookup; selected slots identical'],
 ['Exact-cost cohort',d.phase.no_irq_timing_pairs,'IRQ-overlapped intervals excluded from exact-cycle assertion'],
 ['Cycle delta mean',d.phase.inclusive_cycle_delta.mean,'Candidate minus baseline'],
 ['Cycle delta P95',d.phase.inclusive_cycle_delta.p95,'Candidate minus baseline'],
 ['Cycle delta maximum',d.phase.inclusive_cycle_delta.max,'Candidate minus baseline'],
 ['Calls / normal presented frame',1,'Nine-cycle work budget gain; no guaranteed FPS increase'],
 ['Ownership',d.phase.source,d.phase.method],
 ],[39,26,113]).getRange('A12:C12').format.rowHeight=88;
sheet('Natural audio','Observe the sound clock and original engine-gain phase',
 ['Mode','F10','Native states equal','Worker steps','Tone/FX/envelope equal','All14 equal','R10-only gain differences','Gain formula checks','Observed events'],
 d.natural_audio.map(r=>[r.mode,r.f10?'on':'off',r.native_states_equal,r.worker_steps,r.music_effect_and_envelope_registers_equal,r.all14_psg_equal,r.intentional_engine_gain_differences,r.physical_gain_formula_checks,r.event_latencies.length]),[18,13,23,20,27,19,29,25,23]);
sheet('Latency','Natural flag/death events: worker entry and completed output',
 ['Mode','F10','Event','Native tick','Epoch','Control entry ticks','Control return ticks','Candidate entry ticks','Candidate return ticks'],
 d.natural_audio.flatMap(r=>r.event_latencies.map(e=>[r.mode,r.f10?'on':'off',e.event.event,Number(e.event.native),Number(e.event.epoch),...e.control_entry_return_ticks,...e.candidate_entry_return_ticks])),[17,13,18,19,14,27,27,27,27]);
sheet('PCM','Existing independent sound-only fixtures after real disk boot',['Mode','Full14-register samples','PCM / music result','Scope'],d.pcm.map(r=>[r.mode,r.matching_full_psg_samples,r.candidate.passed?'pass':'FAIL','Synthetic events/velocity; recorded engine/smoke/crash/retrigger/envelope/music, not listening acceptance']),[19,29,25,105]);
sheet('Seals','Canonical ROM, ZIPs and gameplay workbook remain unchanged',['Path','Bytes','SHA256'],d.seals.map(r=>[r.path,r.bytes,r.sha256]),[55,19,99]);
await fs.mkdir(out,{recursive:true});
const name='mapper512-audio-sync.xlsx',file=await SpreadsheetFile.exportXlsx(w);await file.save(path.join(out,name));
const data=await fs.readFile(path.join(out,name));await fs.writeFile(path.join(docs,'measurements/timing',name),data);
const mp=path.join(docs,'measurements/timing/workbooks.json'),m=JSON.parse(await fs.readFile(mp,'utf8'));
m.experimental=(m.experimental||[]).filter(r=>r.path!==`measurements/timing/${name}`);
m.experimental.push({path:`measurements/timing/${name}`,bytes:data.length,sha256:hash(data),ledger:'measurements/timing/mapper512-audio-sync.json',ledger_sha256:hash(raw),
 generator:'scripts/mapper512_audio_sync_workbook.mjs',generator_sha256:hash(await fs.readFile(new URL(import.meta.url))),reference_rom_sha256:d.seals[0].sha256,
 bridge_sha256:d.candidate.bridge_sha256,resource_sha256:d.candidate.resource_sha256,scope:d.status});
await fs.writeFile(mp,JSON.stringify(m,null,2)+'\n');console.log('Wrote separately sealed512KiB audio-sync workbook');
