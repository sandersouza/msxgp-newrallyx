// Experimental full-game ledger only. Never overwrite canonical cartridge timing.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,docs]=process.argv.slice(2);
if(!input||!out||!docs)throw Error('Usage: mapper512_workbook.mjs ledger.json output-directory docs-directory');
const require=createRequire(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/runtime.cjs'));
const artifact=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const hash=b=>createHash('sha256').update(b).digest('hex');
const raw=await fs.readFile(input),d=JSON.parse(raw);
if(d.comparisons.length!==6||d.program.ram_kib!==512||d.f10_family_transitions.length!==4)throw Error('Incomplete experimental matrix');
const w=artifact.Workbook.create();
function sheet(name,title,headers,rows,widths){
 const s=w.worksheets.add(name);s.showGridLines=false;
 const count=rows.length+6;
 const all=s.getRangeByIndexes(0,0,count,headers.length);
 all.format.font={name:'Arial',size:10,color:'#20344A'};all.format.rowHeight=25;
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,count,1).format.columnWidth=v);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:16,bold:true};
 s.getRangeByIndexes(4,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(4,0,1,headers.length).format={fill:'#20344A',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:40};
 if(rows.length)s.getRangeByIndexes(5,0,rows.length,headers.length).values=rows;
 all.format.wrapText=true;s.freezePanes.freezeRows(5);return s;
}
sheet('Scope','512KiB active game: standalone loader pending',['Item','Value','Scope'],[
 ['Status',d.status,'Host/cartridge bootstrap and cold provider; no release'],
 ['Reference cartridge',d.reference_rom_sha256,'Oracle/bootstrap only. Active RAM seals are on Memory.'],
 ['RAM',512,'KiB:32 actual16KiB segments; all owned, no spare hot segment'],
 ['CPU',d.timing.cpu,'Elapsed reference cycles; not accelerated instruction counts'],
 ['Video',d.timing.video,'Refresh differs from gameplay/presentation rate'],
 ['Active timing',d.timing.work,'Self cost and separate commit/VBlank costs not measured'],
 ['Native-clock matched rows',d.comparisons.filter(c=>c.input_clock==='native').reduce((n,c)=>n+c.matched.count,0),'Same camera/state/tick/PSG subset; all shorter in this matrix'],
 ['Unchanged/slower cases','Native-clock3-enemy cadence unchanged','Presentation-clock3-enemy route FPS0.24% lower; trajectory mismatch retained'],
 ['Audio',d.audio,'No waveform or human listening acceptance'],
 ['Cold loading','All four family boundaries tested with F10','F5 transitions; host disk/provider time is not a real loading-time estimate'],
 ['Remaining work',d.program.unresolved.join('; '),'OS context, boot atlas, allocator and real filesystem loading unresolved'],
 ['Limits',d.limits.join(' '),'Not a supported512KiB executable; no physical/PAL acceptance'],
 ],[26,92,87]).getRange('A6:C17').format.rowHeight=62;
const routes=d.comparisons.flatMap(c=>['control','candidate'].map(k=>[c.input_clock,c.enemies,k,c[k].active_frames,
 ...['mean','p95','max'].map(m=>c[k].work[m]/3579545*1000),c[k].presented_fps,c[k].cold_bank_refills]));
const route=sheet('Routes','Inclusive active work; route aggregates are not identical-state proof',
 ['Input clock','Enemies','Program','Active frames','Mean ms','P95 ms','Max ms','Presented FPS','Cold refills'],routes,[21,13,17,17,17,17,17,20,16]);
route.getRange(`E6:H${routes.length+5}`).setNumberFormat('0.000');
const matched=d.comparisons.flatMap(c=>['control','candidate'].map(k=>[c.input_clock,c.enemies,k,c.matched.count,
 ...['mean','p95','max'].map(m=>c.matched[k][m]/3579545*1000),k==='candidate'?c.matched.longer_spans:null]));
const paired=sheet('Matched','Only matching presentation index, camera, native actor state, ticks and PSG',
 ['Input clock','Enemies','Program','Matching frames','Mean ms','P95 ms','Max ms','Longer spans'],matched,[21,13,17,20,17,17,17,19]);
paired.getRange(`E6:G${matched.length+5}`).setNumberFormat('0.000');
sheet('Memory','All32 segments owned; four alternative active layouts', ['Segments','Owner','SHA256 / limit'],[
 ...d.memory.map(r=>[r.segments,r.owner,'16KiB each; no OS/scratch reservation implied']),
 ...d.program.stages.map(r=>[`Family${r.family}`,`${r.bytes} bytes; ${r.code_windows} code windows; ${r.closure_checks} checked entries`,r.sha256]),
 ['Work placeholders','First six segments in each hot image are FF placeholders','These are not loadable ROM/executable images'],
 ],[21,85,81]);
sheet('Cold and F10','Real IRQ, real32 segments and all four family boundaries',
 ['Rounds','Active frames','Cold epochs','Cold refills','IRQ calls','Cache checks','Oracle'],
 d.f10_family_transitions.map(r=>[`${r.native_round} -> ${r.native_round+1}`,r.active_frames,r.cold_epochs,r.cold_bank_refills,r.observed_irqs,r.cache_policy_checks,
 'Maze, HUD and complete cars pass; F10 latch retained']),[20,18,18,18,18,19,79]);
const costs=d.comparisons.flatMap(c=>['control','candidate'].flatMap(k=>c[k].active_costs.map(f=>[
 c.input_clock,c.enemies,k,f.frame,f.work,f.period,f.period-f.work,f.state_sha256])));
sheet('Frame ledger','Reference-cycle elapsed costs; period-work includes wait and commit',
 ['Input clock','Enemies','Program','Frame','Work','Period','Period minus work','State hash'],costs,[21,13,17,13,20,20,26,80]);
await fs.mkdir(out,{recursive:true});
const target=path.join(docs,'measurements/timing/mapper512-integrated.xlsx');
const file=await artifact.SpreadsheetFile.exportXlsx(w),temporary=path.join(out,'mapper512-integrated.xlsx');
await file.save(temporary);
const data=await fs.readFile(temporary),manifestPath=path.join(docs,'measurements/timing/workbooks.json');
await fs.writeFile(target,data);
const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
manifest.experimental=(manifest.experimental||[]).filter(r=>r.path!=='measurements/timing/mapper512-integrated.xlsx');
manifest.experimental.push({path:'measurements/timing/mapper512-integrated.xlsx',sha256:hash(data),bytes:data.length,
 ledger:'measurements/timing/mapper512-integrated.json',ledger_sha256:hash(raw),reference_rom_sha256:d.reference_rom_sha256,
 active_images:d.program.stages.map(r=>({family:r.family,sha256:r.sha256})),generator:'scripts/mapper512_workbook.mjs',
 generator_sha256:hash(await fs.readFile(new URL(import.meta.url))),scope:d.status});
await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({path:target,bytes:data.length,sha256:hash(data),frame_rows:costs.length}));
