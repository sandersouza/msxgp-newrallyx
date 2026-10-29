import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const [input,out]=process.argv.slice(2);
if(!input||!out)throw Error('Usage: component_workbook.mjs summary.json output-directory');
const d=JSON.parse(await fs.readFile(input,'utf8'));
await fs.mkdir(out,{recursive:true});
const w=Workbook.create();
const schedule=d.schedule?w.worksheets.add('Schedule'):null;
const components=w.worksheets.add('Components');
const movement=w.worksheets.add('Movement');
const raster=w.worksheets.add('Raster');
const inputs=w.worksheets.add('Inputs');
const changes=d.comparison?w.worksheets.add('Changes'):null;
const ink='#183153',muted='#526477';
function setup(s,widths,rows){
 s.showGridLines=false;
 s.getRangeByIndexes(0,0,rows,widths.length).format.font={name:'Arial',size:11,color:ink};
 s.getRangeByIndexes(0,0,rows,widths.length).format.rowHeight=25;
 s.getRangeByIndexes(0,0,rows,widths.length).format.verticalAlignment='center';
 widths.forEach((v,i)=>s.getRangeByIndexes(0,i,rows,1).format.columnWidth=v);
 s.freezePanes.freezeRows(5);
}
function title(s,t,sub){s.getRange('A2').values=[[t]];s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:ink};s.getRange('A3').values=[[sub]];s.getRange('A3').format.font={name:'Arial',size:11,color:muted};}
function header(s,range,labels){s.getRange(range).values=[labels];s.getRange(range).format={fill:ink,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:42,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};}
// Inputs hold observed cycle counts. All output time conversions reference B2.
setup(inputs,[43,18,16,16,20,20,20,20,20,20,18,20,95],d.components.length+d.routines.length+110);
inputs.getRange('A2:B4').values=[['CPU clock (Hz)',d.cpu_hz],['Physical refresh (Hz)',d.raster.calibration.refresh_hz],['Target presentation FPS',d.target_presented_fps??29.97]];
inputs.getRange('A5').values=[['SHA256: '+d.rom_sha256]];
inputs.getRange('B2').setNumberFormat('#,##0');inputs.getRange('B3').setNumberFormat('0.00000');
inputs.getRange('B4').setNumberFormat('0.00');
inputs.getRange('D2').values=[[d.machine+'; openMSX 21.0; HUD on; hardware sprite limits on; primary active presentation '+d.presented_fps.toFixed(3)+' FPS']];
inputs.getRange('D3').values=[['Measured active gameplay; death, stopped and bonus intervals excluded at both endpoints.']];
inputs.getRange('D4').values=[['1/2-enemy diagnostics clamp only active population in RAM on the unchanged 3-enemy ROM.']];
header(inputs,'A6:M6',['Measured owner','Frames','Calls','Calls/frame','Mean/frame cycles','P95/frame cycles','Max/frame cycles','Mean/call cycles','P95/call cycles','Max/call cycles','Cycle basis','Tracked terms','Evidence source']);
const rows=d.components.map((r,i)=>({...r,inputRow:i+7}));
inputs.getRange(`A7:M${rows.length+6}`).values=rows.map(r=>[r.label,r.frames,r.calls,r.calls_per_frame,r.frame_cycles.mean,r.frame_cycles.p95,r.frame_cycles.max,r.call_cycles?.mean??null,r.call_cycles?.p95??null,r.call_cycles?.max??null,'Emulated CPU cycles',Object.entries(r.terms).map(([n,k])=>n+(k==='self_cycles'?' [self]':'')).join(' + '),r.source]);
inputs.getRange(`B7:J${rows.length+6}`).setNumberFormat('#,##0.00');
inputs.getRange(`B7:C${rows.length+6}`).setNumberFormat('#,##0');
inputs.tables.add(`A6:M${rows.length+6}`,true,'ComponentInputs');
// Put individual car observations first, while retaining shared owners below.
const car=rows.filter(r=>r.label==='Player graphics'||/enemy graphics|enemy AI decisions/.test(r.label));
const ordered=[...car,...rows.filter(r=>!car.includes(r))];
setup(components,[36,18,18,18,18,18,13,91],ordered.length+12);
title(components,'Measured component costs','Milliseconds per presented gameplay frame; 3 enemies unless the scope specifies otherwise.');
header(components,'A5:H5',['Component','Mean/frame ms','P95/frame ms','Max/frame ms','Mean/call ms','Max/call ms','Calls/frame','Scope / ownership']);
ordered.forEach((r,i)=>{
 const n=i+6,j=r.inputRow;
 components.getRange(`A${n}`).values=[[r.label]];
 components.getRange(`B${n}:G${n}`).formulas=[[
  `=Inputs!E${j}/Inputs!$B$2*1000`,`=Inputs!F${j}/Inputs!$B$2*1000`,`=Inputs!G${j}/Inputs!$B$2*1000`,
  r.call_cycles?`=Inputs!H${j}/Inputs!$B$2*1000`:'',r.call_cycles?`=Inputs!J${j}/Inputs!$B$2*1000`:'',`=Inputs!D${j}`]];
 components.getRange(`H${n}`).values=[[r.scope]];
});
components.getRange(`B6:F${ordered.length+5}`).setNumberFormat('0.000');
components.getRange(`G6:G${ordered.length+5}`).setNumberFormat('0.00');
components.getRange(`H6:H${ordered.length+5}`).format.wrapText=true;
components.getRange(`A6:H${ordered.length+5}`).format.rowHeight=38;
components.tables.add(`A5:H${ordered.length+5}`,true,'ComponentCosts');
components.getRange(`A${ordered.length+7}`).values=[['Inclusive parents overlap children. These rows must not be added as a frame total.']];
components.getRange(`A${ordered.length+8}`).values=[['Player/enemy graphics include dirty uploads; shared motion, actor conversion and SAT publication remain separate.']];
components.getRange(`A${ordered.length+9}`).values=[['Pure music is sequence work. PSG register output is shared with engine/effects and is reported separately.']];
// Preserve the full fine routine ledger in cycles, with inclusive and self costs.
const rh=rows.length+11;
header(inputs,`A${rh}:J${rh}`,['Routine','Calls','Calls/frame','Mean incl. cycles','P95 incl. cycles','Max incl. cycles','Mean self cycles','Self/frame cycles','Ownership','Evidence source']);
inputs.getRange(`A${rh+1}:J${rh+d.routines.length}`).values=d.routines.map(r=>[r.name,r.calls,r.calls_per_frame,r.mean,r.p95,r.max,r.self_mean,r.self_per_frame,'Inclusive minus tracked children for self',r.source]);
inputs.getRange(`B${rh+1}:H${rh+d.routines.length}`).setNumberFormat('#,##0.00');
inputs.getRange(`B${rh+1}:B${rh+d.routines.length}`).setNumberFormat('#,##0');
// Movement groups use actual camera delta, rather than the requested key.
setup(movement,[24,21,12,18,18,18,18,18,18,18,18,18],32);
title(movement,'Horizontal and vertical movement',`Observed camera delta on the same ${d.frames} active frames; workload groups are not matched marginal experiments.`);
header(movement,'A5:H5',['Direction','Transition','Frames','Map mean ms','Map P95 ms','Render mean ms','CPU work mean ms','Interval mean ms']);
const rawStart=20;
header(movement,`A${rawStart}:L${rawStart}`,['Direction','Transition','Frames','Map mean cycles','Map P95 cycles','Map max cycles','Render mean cycles','Render P95 cycles','Work mean cycles','Work P95 cycles','Interval mean cycles','Interval max cycles']);
d.movement.forEach((r,i)=>{
 const n=i+6,j=rawStart+i+1;
 movement.getRange(`A${j}:L${j}`).values=[[r.axis,r.transition,r.samples,r.map.mean,r.map.p95,r.map.max,r.render.mean,r.render.p95,r.work.mean,r.work.p95,r.interval.mean,r.interval.max]];
 movement.getRange(`A${n}:C${n}`).values=[[r.axis,r.transition,r.samples]];
 movement.getRange(`D${n}:H${n}`).formulas=[[`=D${j}/Inputs!$B$2*1000`,`=E${j}/Inputs!$B$2*1000`,`=G${j}/Inputs!$B$2*1000`,`=I${j}/Inputs!$B$2*1000`,`=K${j}/Inputs!$B$2*1000`]];
});
movement.getRange(`D6:H${d.movement.length+5}`).setNumberFormat('0.000');
movement.getRange('A15').values=[['Map = ring preparation + terrain overlays + terrain names/tiles + dirty planning; radar/HUD excluded.']];
movement.getRange('A16').values=[['Render includes map, static HUD and radar; CPU work also includes logic/sprites/commit, excluding HALT.']];
movement.getRange('A17').values=[['A tile crossing compares integer camera tile coordinates at the frame endpoints.']];
movement.getRange('A18').values=[['Source: '+d.profile_path]];
movement.getRange(`D21:L${20+d.movement.length}`).setNumberFormat('#,##0.00');
// Raster endpoints come directly from the VDP clock, independent of CPU epoch.
const cal=d.raster.calibration,rr=Object.entries(d.raster.active_routines);
setup(raster,[29,12,19,20,18,18,18,15,15,15,20,20,20],rr.length+33);
title(raster,'Raster placement of logic and publication','Physical line 0 = VSYNC; 228 CPU cycles per line. Endpoint ranges vary together; no fixed logic scanline.');
header(raster,'A5:J5',['Routine','Calls','Start line min..max','Start cycle min..max','Mean span ms','Mean in VBlank ms','Mean outside ms','Fully in blank','Fully outside','Crosses edge']);
header(raster,'K5:M5',['Mean span cycles','Mean blank cycles','Mean outside cycles']);
rr.forEach(([name,r],i)=>{
 const n=i+6;
 raster.getRange(`A${n}:D${n}`).values=[[name,r.calls,`${r.start_line.min}..${r.start_line.max}`,`${r.start_cpu_cycle_in_line.min}..${r.start_cpu_cycle_in_line.max}`]];
 raster.getRange(`E${n}:G${n}`).formulas=[[`=K${n}/Inputs!$B$2*1000`,`=L${n}/Inputs!$B$2*1000`,`=M${n}/Inputs!$B$2*1000`]];
 raster.getRange(`H${n}:M${n}`).values=[[r.wholly_inside_vblank,r.wholly_outside_vblank,r.crosses_vblank_boundary,r.duration_cycles.mean,r.vblank_cycles.mean,r.outside_vblank_cycles.mean]];
});
raster.getRange(`E6:G${rr.length+5}`).setNumberFormat('0.000');
raster.getRange(`C6:D${rr.length+5}`).format.horizontalAlignment='center';
raster.getRange(`K6:M${rr.length+5}`).setNumberFormat('#,##0.00');
const q=rr.length+9;
header(raster,`A${q}:D${q}`,['Clock / budget','Cycles','Milliseconds','Meaning']);
raster.getRange(`A${q+1}:D${q+7}`).values=[
 ['Physical refresh',cal.cycles_per_refresh,null,'262 lines; 59.922743 Hz'],
 ['Physical VBlank (VR=1)',cal.vblank_cycles,null,'Not a guaranteed usable VRAM budget'],
 ['Usable VBlank reserve',5000,null,'Planning assumption; not measured limit'],
 ['Target presentation budget',null,null,'Nominal NTSC target; physical cadence is separate'],
 ['Maximum atomic commit',d.raster.active_routines.commit.duration_cycles.max,null,`Measured; ${d.raster.active_routines.commit.wholly_inside_vblank}/${d.raster.active_routines.commit.calls} wholly in blank`],
 ['Mean CPU work/frame',d.frame_work_cycles.mean,null,'Excludes synchronization HALT; includes preparation and publication'],
 ['Mean target work margin',null,null,'Mean time margin; tail overruns and refresh alignment still matter']];
raster.getRange(`B${q+4}`).formulas=[['=Inputs!$B$2/Inputs!$B$4']];
raster.getRange(`B${q+7}`).formulas=[[`=B${q+4}-B${q+6}`]];
for(let i=q+1;i<=q+7;i++)raster.getRange(`C${i}`).formulas=[[`=B${i}/Inputs!$B$2*1000`]];
raster.getRange(`B${q+1}:C${q+7}`).setNumberFormat('0.000');
const logic=d.raster.active_routines.Game_Frame,publication=d.raster.active_routines.commit,example=d.raster.example_logic_span;
const notes=[
 'VR rises at physical line 244 + 33 2/3 CPU cycles; falls next line 31 + 33 2/3. Visible picture begins line 32.',
 'Loop: Game_Prepare -> render -> EI/HALT -> commit -> next loop. Foreground work continues during visible scanlines.',
 `Game_Frame begins on physical lines ${logic.start_line.min}..${logic.start_line.max}; ${logic.crosses_vblank_boundary}/${logic.calls} calls cross a VBlank edge.`,
 `Commit begins line ${publication.start_line.min}..${publication.start_line.max}, cycles ${publication.start_cpu_cycle_in_line.min}..${publication.start_cpu_cycle_in_line.max}; IRQ body only acknowledges VBlank and increments the clock.`,
 example?`Observed interval ${example.presentation}: Game_Frame line${example.start_line} cycle${example.start_cpu_cycle_in_line} -> line${example.end_line} cycle${example.end_cpu_cycle_in_line}; ${Number(example.duration).toFixed(0)} cycles.`:'See raw paired endpoints in the raster evidence directory.',
 'Raster spans are inclusive elapsed costs. In-blank/outside costs partition that span; do not add parent and child rows.',
 'Native VDP counter: 1368 ticks/line, 6 ticks/CPU cycle. Every endpoint VR bit and duration was checked.',
 `Measured/control: ${d.raster.presentation_intervals} intervals, ${d.raster.active_intervals} active; states identical; <=${d.raster.control.maximum_absolute_boundary_jitter_cycles.toFixed(0)} cycles boundary jitter.`,
 'Emulator evidence only. No physical hardware certification or new quality reduction.',
 'Refresh '+cal.refresh_hz.toFixed(6)+' Hz; primary active presentation '+d.presented_fps.toFixed(6)+' FPS. These are distinct rates.',
 'Source: '+d.raster_path
];
notes.forEach((v,i)=>raster.getRange(`A${q+9+i}`).values=[[v]]);
if(changes){
 setup(changes,[42,20,20,20,20,83],28);
 title(changes,'Late-frame optimization',`Three-enemy active gameplay: ${d.comparison.frames} before / ${d.frames} current frames; same controller and active filter.`);
 header(changes,'A5:F5',['Measure','Before','Current','Change','Unit','Scope']);
 const before=d.comparison;
 const selected=['HUD static / border','World sprites prepare','World sprites publish','Map drawing'];
 const metrics=[
  ['Presentation',before.presented_fps,d.presented_fps,'FPS','Actual routes differ; this is a scoped run comparison'],
  ['CPU work / frame',before.frame_work_cycles.mean/d.cpu_hz*1000,d.frame_work_cycles.mean/d.cpu_hz*1000,'ms','Excludes synchronization waiting'],
  ['Presentation interval P95',before.frame_interval_cycles.p95/d.cpu_hz*1000,d.frame_interval_cycles.p95/d.cpu_hz*1000,'ms','Tail cadence; not stable 30 FPS']
 ];
 for(const label of selected){
  const b=before.components.find(r=>r.label===label),c=d.components.find(r=>r.label===label);
  if(b&&c)metrics.push([label,b.frame_cycles.mean/d.cpu_hz*1000,c.frame_cycles.mean/d.cpu_hz*1000,'ms','Mean per presented frame; inclusive owners overlap children']);
 }
 if(before.schedule){
  metrics.push(['Late publications',before.schedule.late_frames,d.schedule.late_frames,'frames','Different active sample counts; compare rates below']);
  metrics.push(['Late publication rate',before.schedule.late_frames/before.frames*100,d.schedule.late_frames/d.frames*100,'%','Actual native VDP edges; publications after more than two refreshes']);
 }
 metrics.forEach(([label,b,c,unit,scope],i)=>{const n=i+6;changes.getRange(`A${n}:C${n}`).values=[[label,b,c]];changes.getRange(`D${n}`).formulas=[[`=C${n}-B${n}`]];changes.getRange(`E${n}:F${n}`).values=[[unit,scope]];});
 changes.getRange(`B6:D${metrics.length+5}`).setNumberFormat('0.000');
 changes.getRange('A16').values=[[d.phase_cache_proof?'Applied: four exact VRAM phase sets; inactive-set selection; name buffering remains independent. No native-rule or pixel changes.':'Applied: stable HUD glyph identities, compiled exact phase transfers, clipped sprite copies, cheaper bounds/cache and fixed-slot dispatch.']];
 changes.getRange('A17').values=[[d.phase_cache_proof?`Exact proofs: ${d.phase_cache_proof.transition_probe.cases.toLocaleString('en-US')} transitions, ${d.phase_cache_proof.live_probe.frames} live visible-set guards, ${d.phase_cache_proof.unchanged_payload_count} identical graphics/map payloads.`:'Exact proofs: 999,424 HUD pixels/flag choices; 8,320 transition cases; 3,147 sprite cases; hardware sprite limits retained.']];
 changes.getRange('A18').values=[['Before ROM: '+before.rom_sha256]];
 changes.getRange('A19').values=[['Current ROM: '+d.rom_sha256]];
 changes.getRange('A21').values=[['Before source: '+before.source]];
 changes.getRange('A22').values=[['Current source: '+d.profile_path]];
}
if(schedule){
 const s=d.schedule;
 setup(schedule,[42,19,19,19,30,92],76);
 title(schedule,'Presenter + logic: two-refresh deadline',`${d.frames} active frames; nominal target ${(d.target_presented_fps??29.97).toFixed(2)} FPS; measured two-refresh cadence ${s.measured_two_refresh_fps.toFixed(5)} FPS.`);
 const sr=rh+d.routines.length+4;
 header(inputs,`A${sr}:B${sr}`,['Scheduling input','Observed value']);
 const raw=[['Active frames',s.frames],['Late publications',s.late_frames],['Foreground mean cycles',s.foreground_cycles.mean],['Foreground P95 cycles',s.foreground_cycles.p95],['Foreground max cycles',s.foreground_cycles.max],['Ready margin mean cycles',s.ready_margin_cycles.mean],['Ready margin P05 cycles',s.ready_margin_cycles.p05],['Ready margin minimum cycles',s.ready_margin_cycles.min],['Late shortfall mean cycles',s.late_shortfall_cycles.mean],['Late shortfall P95 cycles',s.late_shortfall_cycles.p95],['Late shortfall max cycles',s.late_shortfall_cycles.max],['Measured two-refresh FPS',s.measured_two_refresh_fps]];
 inputs.getRange(`A${sr+1}:B${sr+raw.length}`).values=raw;
 inputs.getRange(`B${sr+1}:B${sr+raw.length}`).setNumberFormat('#,##0.000');
 header(schedule,'A5:F5',['Deadline result','Observed','Unit','Reference','Status','Interpretation']);
 schedule.getRange('A6').values=[['Foreground ready margin P05']];schedule.getRange('B6').formulas=[[`=Inputs!B${sr+7}/Inputs!$B$2*1000`]];
 schedule.getRange('C6:F6').values=[['ms','Two refreshes','Measured','Negative means the foreground was ready after its target VBlank edge.']];
 schedule.getRange('A7').values=[['Late-frame shortfall mean']];schedule.getRange('B7').formulas=[[`=Inputs!B${sr+9}/Inputs!$B$2*1000`]];
 schedule.getRange('C7:F7').values=[['ms','Late frames only','Measured','Mean work to remove from the critical path in those frames; includes no proposed gain.']];
 schedule.getRange('A8').values=[['Publications after two refreshes']];schedule.getRange('B8').formulas=[[`=Inputs!B${sr+2}/Inputs!B${sr+1}`]];schedule.getRange('B8').setNumberFormat('0.0%');
 schedule.getRange('C8:F8').values=[['frames','Actual VDP edges','Measured','Averages alone do not establish stable presentation cadence.']];
 schedule.getRange('A9').values=[['Nominal target interval']];schedule.getRange('B9').formulas=[['=1000/Inputs!$B$4']];schedule.getRange('C9:F9').values=[['ms','29.97 FPS','Planning','Use alongside the actual physical refresh clock.']];
 schedule.getRange('A10').values=[['Physical two-refresh interval']];schedule.getRange('B10').formulas=[['=2000/Inputs!$B$3']];schedule.getRange('C10:F10').values=[['ms','Measured refresh','Measured','Physical update cadence is not changed to force the nominal target.']];
 schedule.getRange('B6:B7').setNumberFormat('0.000');schedule.getRange('B9:B10').setNumberFormat('0.000');
 schedule.getRange('F6:F10').format.wrapText=true;schedule.getRange('A6:F10').format.rowHeight=40;
 header(schedule,'A13:D13',['Refreshes until publication','Active frames','Share','Meaning']);
 Object.entries(s.refresh_counts).forEach(([n,count],i)=>{const r=14+i;schedule.getRange(`A${r}:B${r}`).values=[[Number(n),count]];schedule.getRange(`C${r}`).formulas=[[`=B${r}/Inputs!B${sr+1}`]];schedule.getRange(`D${r}`).values=[[Number(n)>2?'Missed target':Number(n)===2?'Target cadence':'Earlier publication']];});
 schedule.getRange('C14:C17').setNumberFormat('0.0%');
 header(schedule,'A20:F20',['Foreground owner','Mean all ms','Mean late ms','Max call ms','Current placement','Scheduling / optimization direction']);
 const oh=sr+raw.length+3;
 header(inputs,`A${oh}:D${oh}`,['Foreground self owner','Self/all frame cycles','Self/late frame cycles','Max incl. call cycles']);
 const owners=s.owners.slice(0,10);
 inputs.getRange(`A${oh+1}:D${oh+owners.length}`).values=owners.map(r=>[r.name,r.self_per_frame,r.self_per_late_frame,r.inclusive_max]);
 const directions={
  Ring_UploadNames:'Publish terrain into inactive table; reduce writes or prepare reusable name strips. Current names must be ready before commit.',
  GameBoundary_Upload:'Stable character/color identities skip unchanged color bytes; exact pixels retained. Phase packets still finish before publication.',
  Game_RingPatch:'Terrain event overlays and smoke cache: split work only with current native rings and exact dirty-cell visibility preserved.',
  GameSprites_Prepare:'Car/effect patterns: reuse unchanged preparation; preserve complete cars, masking and sprite limits.',
  Game_Actors:'Cache descriptor conversion when native fields are unchanged; camera projection still needs current coordinates.',
  hud_upload:'Static phase transfer uses the measured burst helper; reuse exact state on each back table. Value events retain scroll compensation.',
  Game_Radar:'Character-dot preparation: current source fast path is measured; further caches must win during moving phases.'
 };
 owners.forEach((r,i)=>{const n=21+i,j=oh+i+1;schedule.getRange(`A${n}`).values=[[r.name]];schedule.getRange(`B${n}:D${n}`).formulas=[[`=Inputs!B${j}/Inputs!$B$2*1000`,`=Inputs!C${j}/Inputs!$B$2*1000`,`=Inputs!D${j}/Inputs!$B$2*1000`]];schedule.getRange(`E${n}:F${n}`).values=[['Foreground',directions[r.name]??'Preserve current native tick/input dependencies; a candidate must reduce measured work before being rescheduled.']];});
 schedule.getRange('B21:D30').setNumberFormat('0.000');schedule.getRange('F21:F30').format.wrapText=true;schedule.getRange('A21:F30').format.rowHeight=46;
 header(schedule,'A33:F33',['Phase / boundary','Mean ms','P95 ms','Max ms','Execution window','Dependency / constraint']);
 const phases=['Game_Prepare','render','wait_blank','commit'];
 const ph=oh+owners.length+3;
 header(inputs,`A${ph}:D${ph}`,['Main phase','Mean cycles','P95 cycles','Max cycles']);
 phases.forEach((name,i)=>{const n=34+i,j=ph+i+1,r=d.raster.active_routines[name];inputs.getRange(`A${j}:D${j}`).values=[[name,r.duration_cycles.mean,r.duration_cycles.p95,r.duration_cycles.max]];schedule.getRange(`A${n}`).values=[[name]];schedule.getRange(`B${n}:D${n}`).formulas=[[`=Inputs!B${j}/Inputs!$B$2*1000`,`=Inputs!C${j}/Inputs!$B$2*1000`,`=Inputs!D${j}/Inputs!$B$2*1000`]];schedule.getRange(`E${n}:F${n}`).values=[[name==='commit'?'Fresh VBlank':name==='wait_blank'?'HALT / synchronization':'Foreground, includes display time',name==='commit'?'Publish registers and HUD/world SAT; every measured commit wholly fits VR.':name==='wait_blank'?'Wait cycles are idle time; moving CPU work inside this wait requires a bounded producer and correct publication.':name==='render'?'Consumes current camera, terrain events and actors; writes inactive pattern/color/name tables.':'Native ticks -> coordinates -> actors/HUD; current input, collision and S/L/bonus rules remain required.']];});
 schedule.getRange('B34:D37').setNumberFormat('0.000');schedule.getRange('E34:F37').format.wrapText=true;schedule.getRange('A34:F37').format.rowHeight=44;
 const commentary=[
  'Ranking uses disjoint SELF time per late frame. Max call is INCLUSIVE and must not be added to parent/child maxima.',
  'Late = actual publication after more than two refresh edges. Ready margin uses the preceding publish edge and wait_blank entry.',
  'Averages hide overload: optimize the measured late-frame path before moving unrelated cheap event/music work.',
  'Earlier scheduling helps only when it reuses work, removes waiting safely, or moves work outside the critical path with validated semantics.',
  d.phase_cache_proof?'Applied: cache four exact fine phases in VRAM; exclude visible set from all background writes. No pause or cadence reduction.':'Applied: stable boundary colors, row-based smoke decoding, unrolled ring metadata and cheaper square loops. No pause or cadence reduction.',
  'Source: '+s.source
 ];commentary.forEach((v,i)=>schedule.getRange(`A${40+i}`).values=[[v]]);
 if(d.packet_transfer){
  const hh=ph+7;
  header(inputs,`A${hh}:C${hh}`,['Transfer bytes','OTIR with RET cycles','Helper with RET cycles']);
  const sizes=[32,64,128,255];
  inputs.getRange(`A${hh+1}:C${hh+sizes.length}`).values=sizes.map(n=>[n,d.packet_transfer.cycles[n].baseline,d.packet_transfer.cycles[n].candidate]);
  header(schedule,'A48:F48',['Transfer bytes','Inline OTIR cycles','CALL/helper cycles','Saved cycles','Saved ms','Isolated helper scope']);
  sizes.forEach((n,i)=>{const row=49+i,j=hh+1+i;schedule.getRange(`A${row}`).values=[[n]];schedule.getRange(`B${row}:E${row}`).formulas=[[`=Inputs!B${j}-11`,`=Inputs!C${j}+18`,`=B${row}-C${row}`,`=D${row}/Inputs!$B$2*1000`]];schedule.getRange(`F${row}`).values=[['47 bytes of code, no RAM; same compiled helper as the gameplay ROM']];});
  schedule.getRange('B49:D52').setNumberFormat('#,##0');schedule.getRange('E49:E52').setNumberFormat('0.000');
  schedule.getRange('A54').values=[['CPU cost correction: RET=11 and CALL=18 cycles in this measured model. Lengths1..31 can cost more; integration is accepted by route timing.']];
  schedule.getRange('A55').values=[['Helper time remains inside HUD/border owners above; do not add this isolated table to the frame ledger.']];
  schedule.getRange('A56').values=[['Source: '+d.packet_transfer.source]];
 }
 if(d.late_frame_proofs||d.hud_sprite_proofs){
  const proofs=d.hud_sprite_proofs??d.late_frame_proofs,lh=ph+17,lastProof=59+proofs.workers.length;
  header(inputs,`A${lh}:F${lh}`,['Isolated worker','Before cycles','Current cycles','Workload / scope','Cycle basis','Evidence source']);
  inputs.getRange(`A${lh+1}:F${lh+proofs.workers.length}`).values=proofs.workers.map(r=>[r.name,r.before,r.after,r.scope,'Mean inclusive cycles; no synchronization',r.source]);
  header(schedule,'A59:F59',['Routine / hook','Before cycles','Current cycles','Saved cycles','Saved ms','Isolated workload / ownership']);
  proofs.workers.forEach((r,i)=>{const n=60+i,j=lh+1+i;schedule.getRange(`A${n}`).values=[[r.name]];schedule.getRange(`B${n}:E${n}`).formulas=[[`=Inputs!B${j}`,`=Inputs!C${j}`,`=B${n}-C${n}`,`=D${n}/Inputs!$B$2*1000`]];schedule.getRange(`F${n}`).values=[[r.scope]];});
  schedule.getRange(`B60:D${lastProof}`).setNumberFormat('#,##0');schedule.getRange(`E60:E${lastProof}`).setNumberFormat('0.000');
  schedule.getRange(`F60:F${lastProof}`).format.wrapText=true;schedule.getRange(`A60:F${lastProof}`).format.rowHeight=38;
  schedule.getRange(`A${lastProof+2}`).values=[['Isolated comparisons explain the change; their costs remain inside the frame owners and must not be added again.']];
  schedule.getRange(`A${lastProof+3}`).values=[[d.hud_sprite_proofs?`ROM ${(proofs.before_rom_bytes/1024).toFixed(0)} -> ${(proofs.rom_bytes/1024).toFixed(0)} KiB; extra ${(proofs.extra_rom_bytes/1024).toFixed(0)} KiB; no extra RAM;50static HUD slots within existing64.`:'Unrolled ring metadata:1,934bytes in unused bank4 ROM; no extra RAM.']];
  schedule.getRange(`A${lastProof+4}`).values=[['All pixels and native rules retained.50Hz changes cadence/tick scheduling; see calculated comparison in Raster.']];
  const ci=lh+proofs.workers.length+3;
  inputs.getRange(`A${ci}:B${ci+1}`).values=[['Before active frames',d.comparison.frames],['Current active frames',d.frames]];
  changes.getRange('B14').formulas=[[`=B13/Inputs!B${ci}*100`]];
  changes.getRange('C14').formulas=[[`=C13/Inputs!B${ci+1}*100`]];

 }
 if(d.phase_cache_proof){
  const p=d.phase_cache_proof;
  header(schedule,'A59:F59',['Phase cache resource / proof','Before','Current','Unit','Window','Interpretation']);
  const items=[['Pattern/color sets',2,p.pattern_sets,'sets','Foreground','Every selected set differs from the visible set.'],['Name tables',2,p.name_tables,'tables','Foreground','Existing two independent terrain name queues.'],['Extra CPU RAM',0,p.extra_ram_bytes,'bytes',p.ram_range,'Four phase keys, selected/visible set and victim cursor.'],['Extra initialized VRAM',0,p.extra_initialized_vram_bytes,'bytes','Upper64KiB','Two additional exact terrain/pattern/color sets.'],['Cartridge size',p.before_rom_bytes/1024,p.rom_bytes/1024,'KiB','ROM','Resident code fits existing bank; immutable graphics payloads unchanged.'],['Native exact transition cases',null,p.transition_probe.cases,'cases','Display on','All64x65 transitions and cold starts in all4 physical sets; full128KiB guards.'],['Live visible-set guards',null,p.live_probe.frames,'renders','Gameplay route','Visible pattern/color bytes unchanged before/after every render.'],['Exact phase cache hits',null,p.live_probe.exact_phase_hits,'renders','Gameplay route','Reuse phase bytes; dynamic radar remains current.']];
  schedule.getRange('A60:F67').values=items;
  schedule.getRange('B60:C67').setNumberFormat('#,##0');schedule.getRange('F60:F67').format.wrapText=true;schedule.getRange('A60:F67').format.rowHeight=42;
  schedule.getRange('A69').values=[['Proof: outputs/fixed-hud/phase-cache-proof.json; first-stage emulator workload, no physical hardware claim.']];
  schedule.getRange('A70').values=[['Late frames remain. Shared game-session/UI integration is tracked separately and is not included in this first-stage measurement.']];
 }
  if(d.video_modes){
   const vi=ph+39,vr=q+22;
   header(inputs,`A${vi}:B${vi}`,['Video timing source','Lines / refresh']);
   inputs.getRange(`A${vi+1}:B${vi+2}`).values=d.video_modes.rows.map(r=>[r.mode,r.lines]);
   inputs.getRange(`A${vi+4}`).values=[[d.video_modes.scope]];
   inputs.getRange(`A${vi+5}`).values=[[d.video_modes.source]];
   header(raster,`A${vr}:F${vr}`,['Video mode','Lines','Cycles/refresh','Refresh ms','Physical Hz','Two-refresh FPS']);
   d.video_modes.rows.forEach((r,i)=>{const row=vr+1+i,j=vi+1+i;raster.getRange(`A${row}`).values=[[r.mode]];raster.getRange(`B${row}:F${row}`).formulas=[[`=Inputs!B${j}`,`=B${row}*228`,`=C${row}/Inputs!$B$2*1000`,`=Inputs!$B$2/C${row}`,`=E${row}/2`]];});
   raster.getRange(`D${vr+1}:F${vr+2}`).setNumberFormat('0.000');raster.getRange(`B${vr+1}:C${vr+2}`).setNumberFormat('#,##0');
   raster.getRange(`A${vr+4}`).values=[['50Hz row is calculated from official timing constants; no50Hz gameplay measurement or ROM change.']];
   raster.getRange(`A${vr+5}`).values=[['Same CPU cycles/second. Reusing the two-refresh cadence gives25.079FPS; near30 needs uneven1/2-refresh intervals and native clock/audio adaptation.']];
  }
}
w.recalculate();
const inspection=await w.inspect({kind:'table',range:'Components!A5:G16',include:'values,formulas',tableMaxRows:12,tableMaxCols:7});
await fs.writeFile(path.join(out,'inspection.json'),JSON.stringify(inspection,null,2));
const errors=await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'Component workbook formula error scan'});
await fs.writeFile(path.join(out,'formula-errors.json'),JSON.stringify(errors,null,2));
for(const [sheetName,range,name] of [['Components','A1:H19','components'],['Components',`A20:H${ordered.length+9}`,'components-detail'],['Movement','A1:H18','movement'],['Raster',`A1:J${q+20}`,'raster'],['Inputs','A1:J18','inputs']]){
 const blob=await w.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
if(changes){const b=await w.render({sheetName:'Changes',range:'A1:F23',scale:1,format:'png'});await fs.writeFile(path.join(out,'changes.png'),new Uint8Array(await b.arrayBuffer()));}
if(schedule){const b=await w.render({sheetName:'Schedule',range:d.packet_transfer?'A1:F57':'A1:F46',scale:1,format:'png'});await fs.writeFile(path.join(out,'schedule.png'),new Uint8Array(await b.arrayBuffer()));}
if(d.late_frame_proofs||d.hud_sprite_proofs||d.phase_cache_proof){const b=await w.render({sheetName:'Schedule',range:'A59:F69',scale:1,format:'png'});await fs.writeFile(path.join(out,'schedule-workers.png'),new Uint8Array(await b.arrayBuffer()));}
if(d.video_modes){const b=await w.render({sheetName:'Raster',range:`A${q+22}:F${q+28}`,scale:1,format:'png'});await fs.writeFile(path.join(out,'video-modes.png'),new Uint8Array(await b.arrayBuffer()));}
const file=await SpreadsheetFile.exportXlsx(w);await file.save(path.join(out,'component-timing.xlsx'));
console.log(path.join(out,'component-timing.xlsx'));
