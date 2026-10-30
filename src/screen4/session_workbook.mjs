import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const [input,out,publishDocs]=process.argv.slice(2);
if(!input||!out)throw Error('Usage: session_workbook.mjs ledger.json output-directory [docs-directory]');
let artifact;
try {artifact=await import('@oai/artifact-tool');}
catch(error) {
 if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;
 const root=process.env.ARTIFACT_TOOL_NODE_ROOT||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node');
 const require=createRequire(path.join(root,'runtime.cjs'));
 artifact=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
}
const {Workbook,SpreadsheetFile}=artifact;
const d=JSON.parse(await fs.readFile(input,'utf8'));
const digest=data=>createHash('sha256').update(data).digest('hex');
const generatorHash=digest(await fs.readFile(new URL(import.meta.url)));
if(publishDocs){
 try {
  const docs=path.resolve(publishDocs);
  const current=JSON.parse(await fs.readFile(path.join(docs,'measurements/timing/workbooks.json'),'utf8')).current;
  if(current&&current.generator_sha256===generatorHash&&current.ledger_sha256===digest(await fs.readFile(input))&&
     current.sha256===digest(await fs.readFile(path.join(docs,'cycle-budget.xlsx')))&&
     current.ledger_sha256===digest(await fs.readFile(path.join(docs,current.ledger)))){
   console.log('Timing workbook already matches this ledger and generator.');
   process.exit(0);
  }
 }catch(error){if(error.code!=='ENOENT')throw error;}
}
const w=Workbook.create();
const summary=w.worksheets.add('Summary'),routines=w.worksheets.add('Routines');
const raster=w.worksheets.add('Raster'),frames=w.worksheets.add('Frames');
const events=w.worksheets.add('Events');
const ink='#20344A';
function setup(s,title,widths,rows){
 s.showGridLines=false;
 const area=s.getRangeByIndexes(0,0,rows,widths.length);
 area.format.font={name:'Arial',size:10,color:ink};area.format.rowHeight=24;
 area.format.verticalAlignment='center';
 widths.forEach((width,i)=>s.getRangeByIndexes(0,i,rows,1).format.columnWidth=width);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:ink};
}
function header(s,range,values){const r=s.getRange(range);r.values=[values];r.format={fill:ink,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},wrapText:true,rowHeight:36,horizontalAlignment:'center',verticalAlignment:'center'};}
setup(summary,`Full session: ${d.enemy_count??3} native enemies`,[36,18,16,79],55);
summary.getRange('A3').values=[['Native round'+(d.native_round??5)+'; active endpoints exclude death, bonus and menus.']];
header(summary,'A5:D5',['Measure','Result','Unit','Scope']);
summary.getRange('A6:A15').values=[['Active presentations'],['Active duration'],['Presentation rate'],['Mean CPU work'],['Late presentations'],['Physical refresh'],['Two-refresh cadence'],['Physical VBlank'],['Mean target work margin'],['Worst readiness margin']];
summary.getRange('C6:D15').values=[['frames','Both endpoints active; no population override'],['s','Sum of active presentation intervals'],['FPS','Short directional sample; not a complete phase'],['ms/frame','Logic, drawing and publication; synchronization excluded'],['frames','Three refreshes instead of two'],['Hz','Physical refresh and presentation rate are separate'],['FPS','Physical emulator clock; nominal target remains29.97'],['ms','Status2 VR; usable reserve is not established by this'],['ms','Average margin does not imply every deadline was met'],['ms','Readiness relative to the second next VBlank edge']];
const end=d.frames.length+5;
summary.getRange('B6:B15').formulas=[
 [`=COUNT('Frames'!A6:A${end})`],[`=SUM('Frames'!C6:C${end})/$B$20`],['=B6/B7'],
 [`=AVERAGE('Frames'!D6:D${end})/$B$20*1000`],[`=COUNTIF('Frames'!B6:B${end},">2")`],
 ['=$B$20/$B$21'],['=$B$20/(2*$B$21)'],['=$B$24/$B$20*1000'],
 [`=($B$20/$B$22-AVERAGE('Frames'!D6:D${end}))/$B$20*1000`],
 [`=MIN('Frames'!E6:E${end})/$B$20*1000`]];
summary.getRange('B6:B15').setNumberFormat('0.000');summary.getRange('B6').setNumberFormat('0');summary.getRange('B10').setNumberFormat('0');
header(summary,'A19:D19',['Clock / assumption','Cycles or rate','Unit','Evidence']);
summary.getRange('A20:D24').values=[
 ['Z80 clock',d.cpu_hz,'Hz','Locked, turbo disabled'],['Physical refresh',d.calibration.cycles_per_refresh,'cycles','262 lines x228 cycles'],
 ['Nominal presentation target',29.97,'FPS','Requested target; distinct from physical two-refresh rate'],
 ['Usable VBlank reserve',5000,'cycles','Planning assumption, not a measured hardware limit'],
 ['Physical VR interval',d.calibration.vblank_cycles,'cycles','Every measured endpoint checked against native VDP status2']];
summary.getRange('A27').values=[['Measured ROM SHA256']];summary.getRange('A28').values=[[d.rom_sha256]];
summary.getRange('A30').values=[['Source revision: '+d.source_revision]];
summary.getRange('A31').values=[[d.machine+'; '+d.emulator.split('\n')[0]+'; HUD/audio and real sprite limits enabled.']];
summary.getRange('A32').values=[[d.control]];
summary.getRange('A33').values=[['Evidence: '+d.profile_path]];
summary.getRange('A34').values=[['Original first-stage workbook remains bound to its earlier ROM and workload.']];
summary.getRange('A35').values=[['Separate checks: '+d.verification.stable_graphics_snapshots+' stable graphics states; '+d.verification.cold_silence_checks+' cold-silence assertions; 16,000 steering refreshes.']];
if(d.mapper_ram_kib===64){
 summary.getRange('A37').values=[['Default 64 KiB RAM; 128 KiB VRAM. See RAM profiles for paired workloads; hardware/full-course acceptance remains open.']];
}
summary.getRange('A45:D45').values=[['Cartridge image',d.rom_bytes,'bytes','Uncompressed programmed image; timing belongs to the ROM hash above.']];
summary.getRange('B45').setNumberFormat('#,##0');
if(d.verification.steering && !d.verification.steering.passed){
 summary.getRange('A36').values=[['Long steering regression FAILED: '+d.verification.steering.distinct_poses_after_refresh5000+' poses after refresh5000; persistent corner stall remains.']];
 summary.getRange('A36').format.font.color='#A12323';
}else if(d.verification.steering){
 summary.getRange('A36').values=[['Corner fallback verified: '+d.verification.steering.distinct_poses_after_refresh5000+' later poses; safe primary movement survives rejected centering.']];
}
if(d.baseline_comparison){
 const b=d.baseline_comparison;
 header(summary,'A38:D38',['Measure','Previous5451bd89','Current','Comparison scope']);
 summary.getRange('A39:B44').values=[['Presentation rate',b.presented_fps],['Late presentations',b.late_frames],['Mean CPU work',b.mean_work_ms],['Active presentations',b.active_frames],['Cold video restore',b.cold_video_mean_ms],['ROM bytes',b.rom_bytes??'n.a.']];
 summary.getRange('C39:C44').formulas=[['=B8'],['=B10'],['=B9'],['=B6'],[`=${d.cold_ledger.find(r=>r.name==='GameSession_Video').inclusive.mean}/$B$20*1000`],[`=${d.rom_bytes}`]];
 summary.getRange('D39:D44').values=[['FPS; same scripted input, trajectories differ'],['Frames; active/death partitions differ'],['ms/frame; synchronization excluded'],['frames; short directional samples'],['ms/call; additional prewarm remains in cold transition'],['bytes; both cartridges remain below the ASCII16 limit']];
 summary.getRange('B39:C44').setNumberFormat('0.000');
 for(const n of [40,42,44])summary.getRange(`B${n}:C${n}`).setNumberFormat('#,##0');
}
header(summary,'A48:D48',['Remaining late frame','CPU work ms','Readiness margin ms','Logic / drawing work']);
d.frames.filter(f=>f.refreshes>2).slice(0,6).forEach((f,i)=>summary.getRange(`A${49+i}:D${49+i}`).values=[[f.frame,f.work_cycles/d.cpu_hz*1000,f.ready_margin/d.cpu_hz*1000,`Game_Prepare ${(f.logic_cycles/d.cpu_hz*1000).toFixed(3)} ms; render ${(f.render_cycles/d.cpu_hz*1000).toFixed(3)} ms`]]);
summary.getRange('B49:C54').setNumberFormat('0.000');
setup(routines,'Measured routine costs',[34,12,16,16,16,16,18,16,16,16,18,18,18,18,18,18,16,16,18,18],d.routines.length+9);
routines.getRange('A3').values=[['Inclusive parents overlap children. Self time subtracts tracked descendants; do not add inclusive rows.']];
routines.getRange('A4').values=[['Zero-call rows have no per-call sample; zero frame cost means the hook was not exercised on this route.']];
header(routines,'A5:T5',['Routine / hook','Calls/frame','Mean incl ms/frame','P95 incl ms/frame','Max incl ms/frame','Self ms/frame','Mean incl cycles/call','P95 incl cycles/call','Max incl cycles/call','Self cycles/frame','Mean incl cycles/frame','P95 incl cycles/frame','Max incl cycles/frame','Mean self cycles/call','P95 self cycles/call','Max self cycles/call','P95 self ms/frame','Max self ms/frame','P95 self cycles/frame','Max self cycles/frame']);
d.routines.forEach((r,i)=>{
 const n=i+6;
 routines.getRange(`A${n}:B${n}`).values=[[r.name,r.calls_per_frame]];
 routines.getRange(`C${n}:F${n}`).formulas=[['K','L','M'].map(k=>`=${k}${n}/'Summary'!$B$20*1000`).concat([`=J${n}/'Summary'!$B$20*1000`])];
 routines.getRange(`G${n}:M${n}`).values=[[r.mean,r.p95,r.max,r.self_per_frame,...['mean','p95','max'].map(k=>r.frame_cycles[k])]];
 routines.getRange(`N${n}:P${n}`).values=[['mean','p95','max'].map(k=>r.self_call_cycles?r.self_call_cycles[k]:'n.a.')];
 if(!r.self_call_cycles)routines.getRange(`N${n}:P${n}`).format.horizontalAlignment='right';
 routines.getRange(`Q${n}:R${n}`).formulas=[['S','T'].map(k=>`=${k}${n}/'Summary'!$B$20*1000`)];
 routines.getRange(`S${n}:T${n}`).values=[['p95','max'].map(k=>r.self_frame_cycles[k])];
});
routines.getRange(`B6:F${d.routines.length+5}`).setNumberFormat('0.000');routines.getRange(`G6:J${d.routines.length+5}`).setNumberFormat('#,##0.0');routines.freezePanes.freezeRows(5);
routines.getRange(`N6:P${d.routines.length+5}`).setNumberFormat('#,##0.0');routines.getRange(`Q6:R${d.routines.length+5}`).setNumberFormat('0.000');routines.getRange(`S6:T${d.routines.length+5}`).setNumberFormat('#,##0.0');
setup(raster,'Logic and publication within the raster',[34,18,19,18,18,18,16,16],d.raster.length+14);
raster.getRange('A3').values=[['Physical line0 = VSYNC;228 CPU cycles/line. Foreground routines have variable placement.']];
header(raster,'A5:H5',['Routine / hook','Start line min..max','Start cycle min..max','Mean in VBlank cycles/call','Mean outside cycles/call','Max in VBlank cycles/call','Wholly in VBlank calls','Wholly outside calls']);
raster.getRange(`A6:H${d.raster.length+5}`).values=d.raster.map(r=>[r.name,`${r.start_line.min}..${r.start_line.max}`,`${r.start_cycle.min.toFixed(3)}..${r.start_cycle.max.toFixed(3)}`,r.blank.mean,r.outside.mean,r.blank.max,r.all_inside,r.all_outside]);
raster.getRange(`D6:F${d.raster.length+5}`).setNumberFormat('#,##0.0');raster.freezePanes.freezeRows(5);
const notes=[
 `VR rises at line${d.calibration.vblank_start_line} cycle${d.calibration.vblank_start_cycle.toFixed(3)} and falls next line${d.calibration.vblank_end_line} cycle${d.calibration.vblank_end_cycle.toFixed(3)}.`,
 'Gameplay logic, PSG and inactive-table drawing run in foreground, including visible scanlines.',
 'Active VBlank IRQ acknowledges VDP status and advances the clock. UI additionally latches keys in its IRQ.',
 'Commit publishes display registers and sprite attribute tables after HALT. See observed endpoints above.',
 'Inclusive spans may cross VBlank. In/outside partitions do not establish a safe VRAM transfer allowance.',
 'UI/cold restoration and flag-capture costs are separate event samples in Events; excluded from active FPS.'
];notes.forEach((n,i)=>raster.getRange(`A${d.raster.length+8+i}`).values=[[n]]);
setup(frames,'Active frame observations',[12,12,18,18,19,18,18,18,18,15,12,12],d.frames.length+8);
frames.getRange('A3').values=[['Raw guest cycles, native VDP cadence and camera endpoints; same recorded workload as the routine ledger.']];
header(frames,'A5:L5',['Frame','Refreshes','Interval cycles','CPU work cycles','Readiness margin cycles','Game_Prepare cycles','Render cycles','Wait cycles','Commit cycles','Untracked cycles','Camera X','Camera Y']);
frames.getRange(`A6:L${end}`).values=d.frames.map(f=>[f.frame,f.refreshes,f.interval_cycles,f.work_cycles,f.ready_margin,f.logic_cycles,f.render_cycles,f.wait_cycles,f.commit_cycles,f.untracked_cycles,f.cx,f.cy]);
frames.getRange(`C6:J${end}`).setNumberFormat('#,##0.0');frames.freezePanes.freezeRows(5);
const costs=[...(d.cold_ledger??[])];
if(d.flag_event)costs.push({name:'GameSession_RemoveFlag',calls:d.flag_event.calls,inclusive:d.flag_event.inclusive,own:d.flag_event.own});
costs.push(...(d.verification.audio.audio_costs??[]));
costs.push(...(d.verification.clear_sequence?.cost_groups??[]));
costs.push(...(d.verification.challenge_speed?.costs??[]));
costs.push(...(d.verification.boot?.title_costs??[]));
costs.push(...(d.verification.enemy_rocks?.cost_groups??[]));
setup(events,'Cold transitions and event costs',[34,10,18,18,18,16,16,16,18,16,18,18,16,16],costs.length+56);
events.getRange('A3').values=[['Controlled samples. Cold hooks: entry to pre-RET. Audio/speed/title/stone fixtures: entry through RET; caller overhead excluded.']];
events.getRange('A4').values=[['Self subtracts tracked children. Do not add inclusive parent and child rows or mix these samples with active FPS.']];
header(events,'A5:N5',['Routine / hook','Calls','Mean incl cycles/call','P95 incl cycles/call','Max incl cycles/call','Mean incl ms/call','P95 incl ms/call','Max incl ms/call','Mean self cycles/call','Mean self ms/call','P95 self cycles/call','Max self cycles/call','P95 self ms/call','Max self ms/call']);
costs.forEach((r,i)=>{
 const n=i+6;
 events.getRange(`A${n}:E${n}`).values=[[r.name,r.calls,r.inclusive.mean,r.inclusive.p95,r.inclusive.max]];
 events.getRange(`F${n}:H${n}`).formulas=[['C','D','E'].map(k=>`=${k}${n}/'Summary'!$B$20*1000`)];
 events.getRange(`I${n}`).values=[[r.own?r.own.mean:'n.a.']];
 if(r.own)events.getRange(`J${n}`).formulas=[[`=I${n}/'Summary'!$B$20*1000`]];
 else {events.getRange(`J${n}`).values=[['n.a.']];events.getRange(`I${n}:J${n}`).format.horizontalAlignment='right';}
 events.getRange(`K${n}:L${n}`).values=[['p95','max'].map(k=>r.own?r.own[k]:'n.a.')];
 if(r.own)events.getRange(`M${n}:N${n}`).formulas=[['K','L'].map(k=>`=${k}${n}/'Summary'!$B$20*1000`)];
 else {events.getRange(`M${n}:N${n}`).values=[['n.a.','n.a.']];events.getRange(`K${n}:N${n}`).format.horizontalAlignment='right';}
});
events.getRange(`C6:E${costs.length+5}`).setNumberFormat('#,##0.0');
events.getRange(`F6:H${costs.length+5}`).setNumberFormat('0.000');
events.getRange(`I6:I${costs.length+5}`).setNumberFormat('#,##0.0');
events.getRange(`J6:J${costs.length+5}`).setNumberFormat('0.000');
events.getRange(`K6:L${costs.length+5}`).setNumberFormat('#,##0.0');events.getRange(`M6:N${costs.length+5}`).setNumberFormat('0.000');
const firstNote=costs.length+8;
[
 'Cold/UI source: '+d.cold_scope.source,
 d.cold_scope.scope,
 'Flag cache invalidation: ten real contact-handler captures; normal and S-hidden caches cleared together.',
 'Challenge callback includes typed glyphs, complete item blits, delay ticks and final wait; this is cold UI only.',
 'AudioStop disables PSG tones/noise, zeroes all three volumes and clears queued effects before blocking work.',
 `Challenge reveal: ${d.challenge_reveal.units} units over ${d.challenge_reveal.nominal_refreshes} physical refreshes; original font/items at 1:1 scale.`,
 `Audio: original WSG challenge loop ${d.audio_assets.challenge_original_ticks} ticks; ${d.audio_assets.challenge_psg_frames} cached PSG frames; ${d.audio_assets.dictionary_entries}/256 dictionary entries.`,
 `Collision: cached attack/hold/release, ${d.audio_assets.crash.frames} sound frames on B/C. AY timbre remains for user acceptance.`,
 'ROM SHA256: '+d.rom_sha256
].forEach((v,i)=>events.getRange(`A${firstNote+i}`).values=[[v]]);
const gainRow=firstNote+11;
header(events,`A${gainRow}:F${gainRow}`,['Engine range','Baseline RMS','Current RMS','Amplitude ratio','Reduction','PCM window']);
for(const [i,r] of d.verification.audio.engine.entries()){
 const n=gainRow+1+i;
 events.getRange(`A${n}:C${n}`).values=[[['Idle','Cruise','Drive'][r.velocity],r.baseline_rms,r.rms]];
 events.getRange(`D${n}:E${n}`).formulas=[[`=C${n}/B${n}`,`=1-D${n}`]];
 events.getRange(`F${n}`).values=[['0.15..1.95s']];
 events.getRange(`B${n}:C${n}`).setNumberFormat('#,##0.0');events.getRange(`D${n}:E${n}`).setNumberFormat('0.0%');
}
const smokeRow=gainRow+5;
if(d.verification.audio.smoke){
 header(events,`A${smokeRow}:F${smokeRow}`,['Smoke cue','15c931 RMS','Current RMS','Amplitude gain','Gain dB','Sound frames']);
 d.verification.audio.smoke.forEach((r,i)=>{
  const n=smokeRow+1+i;
  events.getRange(`A${n}:C${n}`).values=[[r.cue,r.baseline_rms??'n.a.',r.rms]];
  if(r.baseline_rms)events.getRange(`D${n}:E${n}`).formulas=[[`=C${n}/B${n}`,`=20*LOG10(D${n})`]];
  else events.getRange(`D${n}:E${n}`).values=[['n.a.','n.a.']];
  events.getRange(`F${n}`).values=[[r.sound_frames]];
  events.getRange(`B${n}:C${n}`).setNumberFormat('#,##0.0');events.getRange(`D${n}`).setNumberFormat('0.00"x"');events.getRange(`E${n}`).setNumberFormat('0.0');
 });
 events.getRange(`A${smokeRow+4}`).values=[['Captured rising gated tone replaces authored noise. B/C hardware envelope for two sound frames; B then returns to music.']];
 events.getRange(`A${smokeRow+5}`).values=[['Arcade capture: '+d.audio_assets.motion_reference.smoke_bursts+' smoke bursts; engine H/V nominal '+d.audio_assets.motion_reference.engine_hz.toFixed(5)+' Hz. PSG timbre is an approximation.']];
 events.getRange(`A${smokeRow+6}`).values=[['Smoke visual regression: 300 committed frames, all8 H/V fine phases, three native enemies. Phase metadata moved2820..2827; smoke rows remain2800..281F.']];
}
const speedRow=smokeRow+9;
if(d.verification.challenge_speed){
 header(events,`A${speedRow}:F${speedRow}`,['Challenger RND','Arcade target px/tick','Previous cap px/tick','Restored / previous','Enemy cohorts','Scope']);
 d.verification.challenge_speed.arcade.cases.filter(c=>c.parked).forEach((c,i)=>{
  const n=speedRow+1+i;
  events.getRange(`A${n}:C${n}`).values=[[c.display_round,c.player/256,2]];
  events.getRange(`D${n}`).formulas=[[`=B${n}/C${n}`]];
  events.getRange(`E${n}:F${n}`).values=[['Parked','Native target']];
  events.getRange(`E${n}`).format.horizontalAlignment='center';
  events.getRange(`B${n}:C${n}`).setNumberFormat('0.0000');events.getRange(`D${n}`).setNumberFormat('0.0000"x"');
 });
 events.getRange(`A${speedRow+6}`).values=[['Original first credit/start, then seeded native round initializers; no ROM/speed-table edits.64 limiter cases include both signs and fuel-exhaustion activation.']];
 events.getRange(`A${speedRow+7}`).values=[['Real integrated RND3 snapshot: '+d.challenge_motion.observed_per_tick+' px/tick; original target '+d.challenge_motion.target_per_tick+'. Other phases retain their existing cap.']];
}
events.freezePanes.freezeRows(5);
const cosmetics=w.worksheets.add('HUD and startup');
setup(cosmetics,'HUD variants, startup and optional test controls',[34,25,14,79,22,20],60);
cosmetics.getRange('A3').values=[['Active FPS belongs only to the measured compact, TEST_MODE=0 ROM. Variant checks have separate hashes.']];
header(cosmetics,'A5:D5',['Item','Value','Unit','Contract / evidence']);
const boot=d.verification.boot;
const hudPrepare=d.routines.find(r=>r.name==='GameHUD_Prepare');
const hudCommit=d.routines.find(r=>r.name==='GameHUD_Commit');
const detail=[
 ['Selected include',d.hud_module.include,'build-time','No runtime variant dispatch or input staging copies.'],
 ['Full fuel bar',48,'px','Remaining fuel is anchored right; depletion advances from left to right.'],
 ['Red endpoints','2 x 2','px','Columns0..1 and46..47 align exactly with the full bar.'],
 ['Red center','2 x 3','px','Columns23..24, rows56..58. Symmetry axis x=23.5.'],
 ['Yellow markers','6 x 1 x 1','px','Columns6,12,18,29,35,41, row58; existing three fuel sprites.'],
 ['ROUND font','4 x 5','px','White label and number; display cap99. Classic include restores previous RND/gauge.'],
 ['Score display',999999,'cap','Hide leading zeroes; keep one zero. Native counters/rules stay unchanged.'],
 ['HUD Prepare mean',hudPrepare.frame_cycles.mean,'cycles/frame','Foreground inclusive parent cost includes any styling worker.'],
 ['HUD Commit mean',hudCommit.frame_cycles.mean,'cycles/frame','Part of synchronized commit. Do not add to commit inclusive cost.'],
 ['Boot selected states',boot.boot_frames,'states','Lossless hidden-page deltas; bandwidth-limited temporal selection,1:1 crop/RGB333 mapping.'],
 ['Boot measured duration',boot.seconds,'s','One startup-only interval, including decode, upload, IRQs and waits.'],
 ['Boot target duration',boot.target_seconds,'s','Original arcade timing; exact native matrix endpoint, quantized to MSX refreshes.'],
 ['Boot elapsed incl cycles',null,'cycles/call','Not CPU-only. Self and waits are not separated; never add to active-frame work.'],
 ['Boot table / cleanup','D300 / D300..F2FF','RAM','Any key skips; held key consumed until release. UI-only IRQ, no active-game call.'],
 ['Controls normal build',0,'TEST_MODE','Return/equals do not activate new controls.'],
 ['Controls test build',1,'TEST_MODE','Return edges advance; equals toggles car/rock invulnerability. Walls remain solid.'],
 ['Assembly module contracts',20,'contracts','Frozen128 KiB ROM/symbol gate; functional64 KiB adapter is validated separately.'],
];
detail.forEach((r,i)=>cosmetics.getRange(`A${i+6}:D${i+6}`).values=[r]);
cosmetics.getRange('B18').formulas=[["=B16*'Summary'!$B$20"]];
cosmetics.getRange('B13:B14').setNumberFormat('#,##0.0');cosmetics.getRange('B16:B17').setNumberFormat('0.000');cosmetics.getRange('B18').setNumberFormat('#,##0');
header(cosmetics,'A25:F25',['Variant check','Passed','Scenario','ROM SHA256','Mode','Evidence']);
d.verification.build_variants.forEach((r,i)=>cosmetics.getRange(`A${26+i}:F${26+i}`).values=[[
 r.source.includes('-hud-classic')?'classic':r.test_mode?'compact test':'compact normal',r.passed,r.scenario,r.rom_sha256,r.test_mode?1:0,r.source
]]);
header(cosmetics,'A31:F31',['Explosion','70d633 low band','Current low band','Power ratio','Gain dB','Band / method']);
d.verification.audio.crash.forEach((r,i)=>{
 const n=32+i;
 cosmetics.getRange(`A${n}:C${n}`).values=[[r.cue,r.baseline_low_band_power,r.low_band_power]];
 cosmetics.getRange(`D${n}:E${n}`).formulas=[[`=C${n}/B${n}`,`=10*LOG10(D${n})`]];
 cosmetics.getRange(`F${n}`).values=[['30..200Hz; Hann/Goertzel']];
});
cosmetics.getRange('B32:C33').setNumberFormat('#,##0');cosmetics.getRange('D32:E33').setNumberFormat('0.00');
cosmetics.getRange('A36').values=[['Bass100..32Hz borrows B during the cached crash; C retains noise. No PCM/sample-rate ISR. Human timbre acceptance remains pending.']];
cosmetics.getRange('A38').values=[['Boot evidence: '+boot.path]];
header(cosmetics,'A40:D40',['Title / gameplay','Setting','Unit','Scope / verification']);
const titleRows=[
 ['Cast vertical shift',d.title.shift_y,'px','All96 original reveal bitmaps and delays retained; static header checked against pinned source.'],
 ['Keyboard blink',32,'refreshes/half','Only5 and1/2 blink; brackets and all other pixels stay fixed; no reversed text.'],
 ['Brand reference position',d.title.brand_y,'y px',`Supplied artwork on the full screen grid: ${d.title.brand_width}x${d.title.brand_height} at${d.title.brand_x},${d.title.brand_y}; single scale for the complete supplied crop; no generated glyphs.`],
 ['MSX logo','54 x 20 at194,8','px','Uniform3:1 sample of black label; exact8px top/right margins.'],
 ['Optional logo include',d.verification.no_logo.passed,'selected RAM profile','session-ui-options.inc selects session-msx-logo.inc; removing it omits routine, bitmap and call.'],
 ['World S','Red and fixed','behavior','Only radar S blinks; stationary L-before-S regression fails old ROM at radar-144 and passes current ROM.'],
 ['Enemy stone comparison',d.verification.enemy_rocks.cases,'cases','All32 descriptor bytes match original181B/1885 execution; controlled RAM fixtures, no ROM patches.'],
 ['Navigation tag check',d.verification.enemy_rocks.navigation_tag_pairs,'pairs','Spare bit4 tags stones without new RAM; low4 exit bits produce identical decisions for all16 masks/4 headings.'],
];
titleRows.forEach((r,i)=>cosmetics.getRange(`A${41+i}:D${41+i}`).values=[r]);
cosmetics.getRange('D41:D48').format.wrapText=true;
cosmetics.getRange('A41:F48').format.rowHeight=42;
cosmetics.getRange('A50').values=[[d.title.caption]];
cosmetics.getRange('A52').values=[['Logo draw and footer blink are cast-only; detailed inclusive costs are in Events. They never run from active gameplay or the IRQ.']];
cosmetics.getRange('A54').values=[['Active profile includes stone checks; its maximum probe cost is '+Math.round(d.routines.find(r=>r.name==='GameSession_EnemyRockProbe').max)+' cycles, so this short route contains no full recoil.']];
cosmetics.getRange('A58:D58').values=[['Boot skip latency',d.verification.boot_skip.max_skip_latency_ms,'ms max',d.verification.boot_skip.cases+' real key-matrix cases; all11 rows, held-key consumption and initial/mid/matrix skips.']];
cosmetics.getRange('A59:D59').values=[['Boot state timing',boot.max_state_timing_error_ms,'ms max','After initial clearing; absolute publication error within one physical refresh.']];
cosmetics.getRange('A60:D60').values=[['Long steering route',d.verification.steering.passed,'16000 refreshes','Current route: '+d.verification.steering.distinct_poses_after_refresh5000+' later poses. Primary-only fallback passes the original wall lookup.']];
cosmetics.getRange('B58:B59').setNumberFormat('0.000');
cosmetics.getRange('D58:D60').format.wrapText=true;
cosmetics.getRange('A58:F60').format.rowHeight=42;
cosmetics.getRange('A56').values=[['Controlled recoil peak: '+Math.round(d.verification.enemy_rocks.cost_groups.find(r=>r.name==='Enemy stone recoil').inclusive.max)+' cycles. It is separate from active FPS; no event pause is inserted.']];
cosmetics.freezePanes.freezeRows(5);
if(d.verification.clear_sequence){
 const q=d.verification.clear_sequence, sheet=w.worksheets.add('Stage clear');
 setup(sheet,'Last flag: melody, then remaining-fuel bonus',[35,20,20,85,85],34);
 sheet.getRange('A3').values=[['Foreground settlement only; no scanline/VBlank task, no spinning or extra VRAM transfer.']];
 header(sheet,'A5:D5',['Measure','Value','Unit','Scope']);
 sheet.getRange('A6:D7').values=[['Original sound calls',q.original.completion_call,'native ticks','Isolated original2580 execution, request28; includes termination call.'],['Original refresh',q.original.nominal_arcade_hz,'Hz','Physical arcade refresh; separate from MSX presentation cadence.']];
 sheet.getRange('A8:D11').values=[['Original elapsed',null,'s','Sound-only controlled reference, not natural completion.'],['Port melody',53,'updates','Original parts8/9/10; full score length checked by PSG trace.'],['Port update interval',null,'s','Two physical MSX refreshes per audio update.'],['Port score duration',null,'s','One-shot score; fuel conversion starts after request bit5 clears.']];
 sheet.getRange('B8').formulas=[['=B6/B7']];
 sheet.getRange('B10').formulas=[["=2*'Summary'!B21/'Summary'!B20"]];
 sheet.getRange('B11').formulas=[['=B9*B10']];sheet.getRange('B6:B11').setNumberFormat('0.000');sheet.getRange('B6').setNumberFormat('0');sheet.getRange('B9').setNumberFormat('0');sheet.getRange('D6:D13').format.wrapText=true;sheet.getRange('A6:E13').format.rowHeight=36;
 sheet.getRange('A12:D13').values=[['Active selector delta',q.extra_active_selector_cycles_per_call,'cycles/call','One changed conditional branch. Settlement worker has no active-game calls.'],['State / code RAM / VRAM','0 / 33 / 0','bytes','33 code bytes within the existing cold-code reservation; no new state variable, queue, mapper segment or sample ISR.']];
 header(sheet,'A15:E15',['Last flag / pause','Settlement','Pause duration','Fuel held','Evidence']);
 q.cases.forEach((r,i)=>{const c=r.clear_sequence;sheet.getRange(`A${i+16}:E${i+16}`).values=[[c.flag_order.split(' ').at(-1)==='9'?'S':c.flag_order.split(' ').at(-1)==='8'?'L':c.pause_cursor_and_timer_frozen?'ordinary + pause':'ordinary',c.settlement_seconds,c.pause_seconds??0,c.fuel_and_score_stable_during_music,r.source]];});
 sheet.getRange('B16:C20').setNumberFormat('0.000');sheet.getRange('E16:E20').format.wrapText=true;sheet.getRange('A16:E20').format.rowHeight=48;
 sheet.getRange('A23').values=[['Routine inclusive costs are centralized in Events. begin_bonus includes the original converter; do not add parent/child costs.']];
 sheet.getRange('A25').values=[['ROM SHA256: '+d.rom_sha256]];
 sheet.getRange('A27').values=[['Corner-stall fallback has a separate 16000-refresh proof; see Summary and the ROM-bound steering report.']];
 sheet.freezePanes.freezeRows(5);
}
if(d.ram_profile_comparison){
 const q=d.ram_profile_comparison, sheet=w.worksheets.add('RAM profiles');
 setup(sheet,'RAM profiles: retained before / after / mapper',[26,13,14,14,15,17,17,17,17,78],51);
 sheet.getRange('A3').values=[['Same scripted inputs and native populations; trajectories and active/death partitions differ. No matched-frame speedup claim.']];
 header(sheet,'A5:J5',['Profile','Native enemies','Active frames','Presented FPS','Late frames','Mean work ms','P95 work ms','Max work ms','ROM bytes','Measured ROM SHA256']);
 q.profiles.forEach((r,i)=>{
  const n=6+i;
  sheet.getRange(`A${n}:E${n}`).values=[[r.label,r.enemies,r.active_frames,r.presented_fps,r.late_frames]];
  sheet.getRange(`F${n}:H${n}`).formulas=[['mean','p95','max'].map(k=>`=${r.work[k]}/${r.cpu_hz}*1000`)];
  sheet.getRange(`I${n}:J${n}`).values=[[r.rom_bytes,r.rom_sha256]];
 });
 sheet.getRange('D6:D14').setNumberFormat('0.0000');sheet.getRange('F6:H14').setNumberFormat('0.000');sheet.getRange('I6:I14').setNumberFormat('#,##0');
 header(sheet,'A17:F17',['Controlled component','Before cycles','After cycles','Saved cycles','Saved us','Scope']);
 q.component_comparisons.forEach((r,i)=>{
  const n=18+i;
  sheet.getRange(`A${n}:C${n}`).values=[[r.name,r.before_cycles,r.after_cycles]];
  sheet.getRange(`D${n}:E${n}`).formulas=[[`=B${n}-C${n}`,`=D${n}/${q.cpu_hz}*1000000`]];
  sheet.getRange(`F${n}:I${n}`).merge();
  sheet.getRange(`F${n}`).values=[[r.scope]];
  sheet.getRange(`F${n}:I${n}`).format.wrapText=true;
  sheet.getRange(`A${n}:I${n}`).format.rowHeight=44;
 });
 sheet.getRange(`B18:E${17+q.component_comparisons.length}`).setNumberFormat('#,##0.000');
 sheet.getRange('A26:I27').merge();sheet.getRange('A26').values=[[q.scope]];sheet.getRange('A26:I27').format.wrapText=true;
 sheet.getRange('A28').values=[['Cold cache prewarm increased448 cycles (0.125 ms); it runs with display disabled, outside active FPS.']];
 sheet.getRange('A29').values=[['Six-enemy maximum work:48.237 ->49.954 ms; different trajectories. See retained tail analysis; not every maximum improved.']];
 header(sheet,'A31:J31',['Evidence','ROM SHA256','','','','Retained profile directory','','','','']);
 q.profiles.forEach((r,i)=>{
  const n=32+i;
  sheet.getRange(`B${n}:E${n}`).merge();sheet.getRange(`F${n}:J${n}`).merge();
  sheet.getRange(`A${n}`).values=[[r.label+' / '+r.enemies]];sheet.getRange(`B${n}`).values=[[r.rom_sha256]];sheet.getRange(`F${n}`).values=[[r.profile_path]];
  sheet.getRange(`B${n}:J${n}`).format.wrapText=true;sheet.getRange(`A${n}:J${n}`).format.rowHeight=44;
 });
 sheet.freezePanes.freezeRows(5);
}
w.recalculate();
await fs.mkdir(out,{recursive:true});
const inspected=await w.inspect({kind:'table',range:'Summary!A5:D15',include:'values,formulas',tableMaxRows:11,tableMaxCols:4});
await fs.writeFile(path.join(out,'workbook-check.ndjson'),inspected.ndjson);
const errors=await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30}});
await fs.writeFile(path.join(out,'workbook-errors.ndjson'),errors.ndjson);
if(/"kind":"match"/.test(errors.ndjson))throw Error('Unexpected formula error; inspect workbook-errors.ndjson');
for(const [s,range] of [['Summary','A1:D24'],['Routines','A1:J18'],['Raster','A1:H18'],['Frames','A1:L15'],['Events',`A1:J${firstNote+8}`]]){
 const image=await w.render({sheetName:s,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,s.toLowerCase()+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const lower=await w.render({sheetName:'Routines',range:'A24:J40',scale:1,format:'png'});
await fs.writeFile(path.join(out,'routines-hooks.png'),new Uint8Array(await lower.arrayBuffer()));
const provenance=await w.render({sheetName:'Summary',range:'A26:D36',scale:1,format:'png'});
await fs.writeFile(path.join(out,'summary-evidence.png'),new Uint8Array(await provenance.arrayBuffer()));
if(d.ram_profile_comparison){
 const img=await w.render({sheetName:'RAM profiles',range:'A1:I29',scale:1,format:'png'});
 await fs.writeFile(path.join(out,'ram-profiles.png'),new Uint8Array(await img.arrayBuffer()));
}
for(const [s,range,file] of [['Summary','A37:D52','comparison.png'],['Events',`A${gainRow}:F${gainRow+3}`,'engine-gain.png'],['Routines','A19:J36','routines-middle.png'],['Routines','A37:J50','routines-tail.png']]){
 const render=await w.render({sheetName:s,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,file),new Uint8Array(await render.arrayBuffer()));
}
if(d.verification.audio.smoke){
 const render=await w.render({sheetName:'Events',range:`A${smokeRow}:N${smokeRow+6}`,scale:1,format:'png'});
 await fs.writeFile(path.join(out,'smoke-gain.png'),new Uint8Array(await render.arrayBuffer()));
}
if(d.verification.challenge_speed){
 const render=await w.render({sheetName:'Events',range:`A${speedRow}:N${speedRow+7}`,scale:1,format:'png'});
 await fs.writeFile(path.join(out,'challenge-speed.png'),new Uint8Array(await render.arrayBuffer()));
}
for(const [s,range,file] of [['Routines','N5:T18','routines-self.png'],['Events','K5:N10','events-self.png']]){
 const render=await w.render({sheetName:s,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,file),new Uint8Array(await render.arrayBuffer()));
}
w.recalculate();
console.log((await w.inspect({kind:'table',range:'Summary!A5:D15',include:'values,formulas',tableMaxRows:11,tableMaxCols:4})).ndjson);
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:10},summary:'Final formula errors'})).ndjson);
const file=await SpreadsheetFile.exportXlsx(w);await file.save(path.join(out,'cycle-budget.xlsx'));
const cosmeticImage=await w.render({sheetName:'HUD and startup',range:'A1:F22',scale:1,format:'png'});
await fs.writeFile(path.join(out,'hud-startup.png'),new Uint8Array(await cosmeticImage.arrayBuffer()));
const titleImage=await w.render({sheetName:'HUD and startup',range:'A40:D60',scale:1,format:'png'});
await fs.writeFile(path.join(out,'title-controls.png'),new Uint8Array(await titleImage.arrayBuffer()));
if(d.verification.clear_sequence){
 const img=await w.render({sheetName:'Stage clear',range:'A1:E27',scale:1,format:'png'});
 await fs.writeFile(path.join(out,'stage-clear.png'),new Uint8Array(await img.arrayBuffer()));
}
console.log(path.join(out,'cycle-budget.xlsx'));
if(publishDocs){
 const docs=path.resolve(publishDocs),timing=path.join(docs,'measurements/timing');
 const target=path.join(docs,'cycle-budget.xlsx');
 await fs.mkdir(timing,{recursive:true});
 const manifestPath=path.join(timing,'workbooks.json');
 let manifest={historical:[]};
 try {manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));}
 catch(error){if(error.code!=='ENOENT')throw error;}
 const data=await fs.readFile(path.join(out,'cycle-budget.xlsx'));
 try {
  const previous=await fs.readFile(target),sha=digest(previous);
  if(sha!==digest(data)&&!manifest.historical.some(row=>row.sha256===sha)){
   const relative=`measurements/timing/archive/retained-${sha.slice(0,16)}/cycle-budget.xlsx`;
   await fs.mkdir(path.dirname(path.join(docs,relative)),{recursive:true});
   await fs.writeFile(path.join(docs,relative),previous);
   const retained={source:'Previous docs/cycle-budget.xlsx',path:relative,bytes:previous.length,sha256:sha,scope:'Historical workbook; retain its embedded ROM hash and workload.'};
   if(manifest.current?.sha256===sha&&manifest.current.ledger){
    const priorLedger=await fs.readFile(path.join(docs,manifest.current.ledger));
    if(digest(priorLedger)!==manifest.current.ledger_sha256)throw Error('Previous workbook ledger hash changed');
    retained.ledger=path.posix.join(path.posix.dirname(relative),'cycle-ledger.json');
    retained.ledger_sha256=digest(priorLedger);retained.rom_sha256=manifest.current.rom_sha256;
    await fs.writeFile(path.join(docs,retained.ledger),priorLedger);
   }
   manifest.historical.push(retained);
  }
 }catch(error){if(error.code!=='ENOENT')throw error;}
 const ledger=await fs.readFile(input);
 await fs.writeFile(path.join(timing,'cycle-ledger.json'),ledger);
 manifest.current={path:'cycle-budget.xlsx',bytes:data.length,sha256:digest(data),rom_sha256:d.rom_sha256,
  rom_bytes:d.rom_bytes,ledger:'measurements/timing/cycle-ledger.json',ledger_sha256:digest(ledger),
  generator:'src/screen4/session_workbook.mjs',generator_sha256:generatorHash,scope:d.workload};
 await fs.writeFile(target+'.tmp',data);await fs.rename(target+'.tmp',target);
 await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
 console.log('Maintained workbook:',target);
}
