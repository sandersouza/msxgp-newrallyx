// Cold-I/O evidence only; never replace the canonical gameplay workbook.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,docs]=process.argv.slice(2);
if(!input||!out||!docs)throw Error('Usage: mapper512_cold_workbook.mjs ledger.json output-directory docs-directory');
const require=createRequire(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/runtime.cjs'));
const artifact=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const raw=await fs.readFile(input),d=JSON.parse(raw),hash=b=>createHash('sha256').update(b).digest('hex');
if(d.filesystem_runs.length!==16||d.active_occupied_checks.length!==3||d.f10_occupied_transitions.length!==4)throw Error('Incomplete cold/occupied matrix');
const w=artifact.Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const all=s.getRangeByIndexes(0,0,rows.length+6,headers.length);
 all.format.font={name:'Arial',size:10,color:'#20344A'};all.format.rowHeight=27;all.format.wrapText=true;
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,rows.length+6,1).format.columnWidth=v);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={bold:true,size:16};
 s.getRangeByIndexes(4,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(4,0,1,headers.length).format={fill:'#20344A',font:{bold:true,color:'#FFFFFF'},rowHeight:42,wrapText:true};
 if(rows.length)s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;
 s.freezePanes.freezeRows(5);return s;
}
const plan=d.plans[1],hz=3579545;
sheet('Scope','512KiB cold I/O: native boot/callback integration pending',['Item','Value','Limit'],[
 ['Status',d.status,'No release; ignored diagnostic executables only'],
 ['Physical RAM',512,'KiB,32 actual segments; no cartridge in filesystem cases'],
 ['Scattered storage',48,'KiB: OS32 plus world shadow16; declared holes, not extra banks'],
 ['Bridge',plan.bridge.sha256,`${plan.bridge.bytes} bytes, bank30 offset1000`],
 ['Active workload','Three/five/six enemies;465 matching state/PSG samples','Occupied holes use a host fixture; not filesystem/game handoff'],
 ['F10','Four occupied-layout family boundaries pass','Actual boot-held key in active tests; filesystem fixture uses only a lifetime marker'],
 ['Cold cycles',d.cycle_ledger.units,'Read + EndBatch are disjoint siblings; self cycles unmeasured'],
 ['Video',d.cycle_ledger.video,'Refresh is distinct from gameplay/presentation rate'],
 ['Remaining',d.remaining.join('; '),'No standalone512KiB game qualification'],
 ['Limits',d.limits.join(' '),'No hardware, PAL or listening acceptance'],
 ],[26,91,87]).getRange('A6:C15').format.rowHeight=62;
sheet('Memory','Cold ownership within the same32 physical segments',['Owner','Bytes','Lifetime'],[
 ['OS snapshots in common holes',32768,`${plan.context_fragments} fragments; persists while gameplay owns4/5`],
 ['World-half shadow in common holes',16384,`${plan.map_staging_fragments} fragments; survives the final DMA/decode`],
 ['Bridge/directory',plan.bridge.bytes,'Bank30:5000 onward; code below7C00, initial SP7D00'],
 ['Reserved bridge hole',0x2e40,'Offset1000..3E3F; not a new segment'],
 ['Compressed DMA segment2',16384,'Borrow world map only while stopped'],
 ['Decoded output segment3',16384,'Borrow world map; restore from shadow after final disk call'],
 ['OS segments4/5',32768,'Borrow both flag caches; rebuild before gameplay'],
 ['Game state0/main1',32768,'Preserved throughout; synthetic in cold-only test'],
 ['Occupied active images',4,'Separate exact hashes in source ledger; original active bytes unchanged'],
 ],[39,19,104]);
const runs=d.filesystem_runs.filter(r=>!r.negative);
sheet('Cold comparison','Same120 resources and both maps; total includes finalization',
 ['Mode','OS/file batching','Read mean ms','Read P95 ms','Read max ms','End mean ms','Total seconds','Open/close','Block reads'],
 runs.map(r=>[r.mode,r.os_context_batching,...['mean','p95','max'].map(k=>r.cold_cycles[k]/hz*1000),r.batch_flush_cycles.mean/hz*1000,r.total_cold_cycles/hz,
 `${r.filesystem_calls.open}/${r.filesystem_calls.close}`,r.filesystem_calls.read_blocks]),[17,20,20,20,20,20,21,18,20]);
sheet('Phases','Inclusive cold work, virtual directory-backed floppy; not physical loading time',
 ['Mode','Batching','Sequence','Family','Resources','Elapsed seconds'],
 runs.flatMap(r=>r.phase_costs.map((p,i)=>[r.mode,r.os_context_batching,i,p.family,p.reads,p.cycles/hz])),[17,19,18,18,20,23]);
sheet('Verification','Capacity/errors, real filesystem and occupied active game are separate',
 ['Mode','RAM KiB','Fault','Reads','Cold flushes','World checks','Scope'],
 d.filesystem_runs.map(r=>[r.mode,r.ram_kib,r.fault||'none',r.resource_reads,r.batch_flushes,r.filesystem_calls?.world_half_checks??null,r.scope]),
 [16,16,20,16,18,20,112]);
sheet('Occupied gameplay','Cold storage populated; inclusive active work and matched subsets',
 ['Round','Program','Active','Mean ms','P95 ms','Max ms','Presented FPS','Matching frames'],
 d.active_occupied_checks.flatMap(r=>['control','occupied'].map(k=>[r.round,k,r[k].active_frames,...['mean','p95','max'].map(v=>r[k].work[v]/hz*1000),hz/r[k].period.mean,r.matching_rows])),
 [16,20,17,20,20,20,22,23]);
sheet('Cold ledger','Function intervals in reference cycles; no sum of nested parents',
 ['Mode','Batching','Function','Call','Inclusive cycles'],
 runs.flatMap(r=>[...r.resource_costs.map((c,i)=>[r.mode,r.os_context_batching,'Read',i,c]),...r.flush_costs.map((c,i)=>[r.mode,r.os_context_batching,'EndBatch',i,c])]),
 [17,20,24,17,27]);
await fs.mkdir(out,{recursive:true});
const temp=path.join(out,'mapper512-cold-io.xlsx'),file=await artifact.SpreadsheetFile.exportXlsx(w);await file.save(temp);
const data=await fs.readFile(temp),target=path.join(docs,'measurements/timing/mapper512-cold-io.xlsx');await fs.writeFile(target,data);
const mp=path.join(docs,'measurements/timing/workbooks.json'),m=JSON.parse(await fs.readFile(mp,'utf8'));
m.experimental=(m.experimental||[]).filter(r=>r.path!=='measurements/timing/mapper512-cold-io.xlsx');
m.experimental.push({path:'measurements/timing/mapper512-cold-io.xlsx',bytes:data.length,sha256:hash(data),ledger:'measurements/timing/mapper512-cold-io.json',
 ledger_sha256:hash(raw),generator:'scripts/mapper512_cold_workbook.mjs',generator_sha256:hash(await fs.readFile(new URL(import.meta.url))),
 reference_rom_sha256:plan.reference_rom_sha256,bridge_sha256:plan.bridge.sha256,scope:d.status});
await fs.writeFile(mp,JSON.stringify(m,null,2)+'\n');console.log(JSON.stringify({path:target,bytes:data.length,sha256:hash(data)}));
