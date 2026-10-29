// Run with @oai/artifact-tool installed or the bundled runtime's node_modules.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [source, outputDir] = process.argv.slice(2);
if (!source || !outputDir) throw new Error('Usage: workbook.mjs summary.json output-directory');
const d = JSON.parse(await fs.readFile(source, 'utf8'));
const actionOnly=!!d.primary_action_only;
await fs.mkdir(outputDir, { recursive: true });
const wb = Workbook.create();
const budget = wb.worksheets.add('Budget');
const movement = d.movement_groups?.length ? wb.worksheets.add('Movement') : null;
const routines = wb.worksheets.add('Routines');
const frames = wb.worksheets.add('Frames');
const sources = wb.worksheets.add('Sources');
const comparison=d.optimization_comparison?wb.worksheets.add('Optimization'):null;
const multi=d.multi_car_workloads?.length?wb.worksheets.add('MultiCar'):null;
const multiCosts=multi?wb.worksheets.add('MultiCarCosts'):null;
const cache=d.synthetic_smoke_cache?wb.worksheets.add('SmokeCache'):null;
const dirty=d.synthetic_dirty_names?wb.worksheets.add('DirtyNames'):null;
const ink = '#183153', blue = '#2563EB', gray = '#526477';
function setup(sh, end, widths) {
  sh.showGridLines = false;
  sh.getRange(`A1:${end}`).format.font = {name:'Arial',size:11,color:ink};
  sh.getRange(`A1:${end}`).format.rowHeight = 23;
  widths.forEach((w,i) => sh.getRangeByIndexes(0,i,Number(end.match(/\d+/)[0]),1).format.columnWidth=w);
  sh.freezePanes.freezeRows(5);
}
function title(sh, text) {
  sh.getRange('A2').values=[[text]];
  sh.getRange('A2').format.font={name:'Arial',size:18,bold:true,color:ink};
}
function header(sh, range, vals) {
  sh.getRange(range).values=[vals];
  sh.getRange(range).format={fill:ink,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,verticalAlignment:'center',horizontalAlignment:'center',rowHeight:36};
}
function table(sh, range, name) {
  sh.tables.add(range,true,name);
}
setup(budget,'F33',[43,20,20,20,3,91]);
setup(routines,`L${d.routines.length+9}`,[25,42,12,12,15,15,15,15,15,17,15,17]);
setup(frames,`U${d.frames.length+5}`,[10,10,10,12,17,17,17,17,17,17,17,15,15,18,31,10,10,10,10,15,17]);
setup(sources,'D31',[33,24,3,117]);
budget.tabColor=ink;
title(budget,'Fixed HUD cycle budget');
budget.getRange('A3').values=[[`Measured lab workload: ${d.measured_frames} frames, original clock, 50 Hz video`]];
header(budget,'A5:D5',['Measured result','Mean','Maximum','Unit']);
budget.getRange('A6:A10').values=[['Active work per presentation'],['Presentation interval'],['Presented frames / second'],['Atomic VDP commit'],['Drawing work over 60 Hz budget']];
const last=d.frames.length+5;
budget.getRange('B6:D10').values=[
  [null,null,'ms'],[null,null,'ms'],[null,null,'FPS'],[null,null,'cycles'],[null,null,'frames']];
budget.getRange('B6:C9').formulas=[
  [`=AVERAGE(Frames!L6:L${last})`,`=MAX(Frames!L6:L${last})`],
  [`=AVERAGE(Frames!M6:M${last})`,`=MAX(Frames!M6:M${last})`],
  ['=1000/B7','=MIN(1000/MIN(Frames!M6:M'+last+'),Sources!B4/Sources!B5)'],
  [`=AVERAGE(Frames!I6:I${last})`,`=MAX(Frames!I6:I${last})`]];
budget.getRange('B10').formulas=[[`=COUNTIF(Frames!N6:N${last},"<0")`]];
budget.getRange('A11').values=[['Work over 30 FPS budget']];
budget.getRange('B11').formulas=[[`=COUNTIF(Frames!K6:K${last},">"&Sources!B4/Sources!B8)`]];
budget.getRange('D11').values=[['frames']];
budget.getRange('B6:C8').setNumberFormat('0.00');
budget.getRange('B9:C10').setNumberFormat('#,##0');
budget.getRange('F6').values=[['Active work excludes wait_blank, which contains HALT and its wake-up ISR.']];
budget.getRange('F8').values=[['Maximum FPS is bounded by physical refresh; publication intervals include varying commit duration.']];
budget.getRange('F7').values=[['Cadence alternates between one and two refreshes. Average FPS is not stable FPS.']];
budget.getRange('F9').values=[['Commit costs do not include VRAM preparation, which runs on back buffers.']];
header(budget,'A13:D13',['Planning budget','Cycles','Time (ms)','Status']);
budget.getRange('A14:A19').values=[['Current 50 Hz video refresh'],['60 Hz video drawing interval'],['Two 60 Hz refreshes'],['VBlank work reserve'],['Target presentation interval'],['Current mean work: 60 Hz margin']];
budget.getRange('B14:D19').values=[
  [null,null,'Current'],[null,null,'Planning'],[null,null,'Planning'],[null,null,'Assumption'],[null,null,'Goal'],[null,null,'Measured']];
budget.getRange('B14:C19').formulas=[
  ['=Sources!B5','=B14/Sources!B4*1000'],
  ['=Sources!B6','=B15/Sources!B4*1000'],
  ['=B15*2','=B16/Sources!B4*1000'],
  ['=Sources!B7','=B17/Sources!B4*1000'],
  ['=Sources!B4/Sources!B8','=1000/Sources!B8'],
  [`=B15-AVERAGE(Frames!K6:K${last})`,'=B19/Sources!B4*1000']];
budget.getRange('A20').values=[['Mean work: 30 FPS remaining budget']];
budget.getRange('B20:C20').formulas=[[`=B18-AVERAGE(Frames!K6:K${last})`,'=B20/Sources!B4*1000']];
budget.getRange('D20').values=[['Measured']];
budget.getRange('B20').setNumberFormat('#,##0');
budget.getRange('C20').setNumberFormat('0.000');
budget.getRange('B14:B19').setNumberFormat('#,##0');
budget.getRange('C14:C19').setNumberFormat('0.000');
budget.getRange('B19:C19').conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{fill:'#FEE2E2',font:{color:'#B91C1C'}}});
budget.getRange('F15').values=[['60 Hz is a planning comparison. This task does not switch the ROM from 50 Hz.']];
budget.getRange('F16').values=[['Two refreshes allow near-30 FPS only with a deliberate, bounded scheduler.']];
budget.getRange('F17').values=[['5,000 cycles is a provisional usable-work reserve, not a measured VBlank length.']];
budget.getRange('F18').values=[['Approximately 30 FPS is the goal; all quality and pause acceptance belongs to the user.']];
header(budget,'A22:D22',['Scheduling candidate','State','Budget (cycles)','Acceptance']);
budget.getRange('A23:D25').values=[
  ['Flag-capture event pause','Proposed','Not measured','User decides'],
  ['Deferred expensive hook','Proposed','Not measured','Measure first'],
  ['Further graphical reduction','Proposed','Not measured','User decides']];
budget.getRange('F23').values=[['Measure exact pause duration, hook cost and input behavior before gameplay adoption.']];
budget.getRange('F24').values=[['Record whether an operation must finish in VBlank or can prepare an inactive buffer.']];
budget.getRange('F25').values=[['No flag-capture pause or new visual reduction was introduced by this profiling work.']];
budget.getRange('A28').values=[['Scope: free-camera laboratory; game logic, AI, collisions and audio are not exercised.']];
budget.getRange('A29').values=[[`Control run: identical ${d.measured_frames} camera/tick states and total time; boundary jitter up to 5 cycles.`]];
budget.getRange('A30').values=[['Routine self costs reconcile with total frame time after loop overhead. See Sources for definitions.']];

title(routines,actionOnly?'Three-enemy action: routine costs':'Routine and hook costs');
routines.getRange('A3').values=[['Cycles per call include guest timing and waits. Never sum inclusive parents and children.']];
header(routines,'A5:L5',['Routine / hook','Purpose','Calls','Calls/frame','Min incl.','Mean incl.','P95 incl.','Max incl.','Mean self','Self / frame','Mean incl. ms','Self/frame % refresh']);
const nr=d.routines.length+5;
routines.getRange(`A6:J${nr}`).values=d.routines.map(r=>[r.name,r.purpose.replace(' (not called in this workload)',''),r.calls,r.calls_per_frame,r.min,r.mean,r.p95,r.max,r.self_mean,r.self_total/d.measured_frames]);
routines.getRange('K6:L6').formulas=[['=F6/Sources!$B$4*1000','=J6/Sources!$B$5']];
routines.getRange(`K6:L${nr}`).fillDown();
d.routines.forEach((r,i)=>{if(!r.calls)routines.getRange(`K${i+6}`).values=[[null]];});
routines.getRange(`C6:C${nr}`).setNumberFormat('#,##0');
routines.getRange(`D6:D${nr}`).setNumberFormat('0.00');
routines.getRange(`E6:J${nr}`).setNumberFormat('#,##0');
routines.getRange(`K6:K${nr}`).setNumberFormat('0.000');
routines.getRange(`L6:L${nr}`).setNumberFormat('0.0%');
table(routines,`A5:L${nr}`,'RoutineCosts');
routines.getRange(`A${nr+2}`).values=[['P95 = nearest-rank 95th percentile. ISR entry/vector latency is charged to its interrupted context.']];
routines.getRange(`A${nr+3}`).values=[['Self = inclusive minus tracked child spans; untracked helpers remain in their nearest measured owner.']];
routines.getRange(`A${nr+4}`).values=[['Zero calls and blank call timings mean unobserved in this workload; use separate synthetic bounds for those hooks.']];

title(frames,'Per-presentation cycle ledger');
frames.getRange('A3').values=[[actionOnly?`Active intervals within software frames ${d.frames[0].frame}..${d.frames.at(-1).frame}; death/bonus/stopped rows omitted. Negative margin exceeds one refresh.`:`Software frames ${d.frames[0].frame}..${d.frames.at(-1).frame}; warmed start. Negative margin exceeds the proposed single-60-Hz draw interval.`]];
header(frames,'A5:N5',['Frame','Camera X','Camera Y','Input ticks','Total cycles','Input cycles','Render cycles','Wait cycles','Commit cycles','Loop + outside IRQ','Work cycles','Work ms','Interval ms','60 Hz margin cycles']);
frames.getRange(`A6:J${last}`).values=d.frames.map(r=>[r.frame,r.cx,r.cy,r.elapsed_ticks,r.cycles,r.input??r.Game_Prepare,r.render,r.wait_blank,r.commit,r.loop_overhead]);
frames.getRange('K6:N6').formulas=[['=F6+G6+I6+J6','=K6/Sources!$B$4*1000','=E6/Sources!$B$4*1000','=Sources!$B$6-K6']];
frames.getRange(`K6:N${last}`).fillDown();
frames.getRange(`A6:K${last}`).setNumberFormat('#,##0');
frames.getRange(`L6:M${last}`).setNumberFormat('0.000');
frames.getRange(`N6:N${last}`).setNumberFormat('#,##0');
frames.getRange(`N6:N${last}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{fill:'#FEE2E2',font:{color:'#B91C1C'}}});
header(frames,'O5:U5',['Movement command','Delta X','Delta Y','Fine X','Fine Y','Camera tile crossing','Name strip calls']);
frames.getRange(`O6:U${last}`).values=d.frames.map(r=>[r.command??null,r.dx??null,r.dy??null,r.phase_x??null,r.phase_y??null,r.tile_crossing===undefined?null:r.tile_crossing?'Yes':'No',r.Ring_UploadColumn_calls===undefined?null:r.Ring_UploadColumn_calls+r.Ring_UploadRow_calls]);
frames.getRange(`P6:S${last}`).setNumberFormat('0');
table(frames,`A5:U${last}`,'FrameCosts');

if (movement) {
  setup(movement,'L53',[16,13,18,12,17,17,17,14,14,15,15,17]);
  title(movement,'Movement cost by axis and tile crossing');
  movement.getRange('A3').values=[['Both directions pooled. Camera crossings and delayed back-table updates are distinct events.']];
  header(movement,'A5:L5',['Axis','Speed','Camera transition','Frames','Mean cycles','P95 cycles','Max cycles','Mean ms','Max ms','Average FPS','Over 16.69 ms','Over 33.38 ms']);
  const end=d.movement_groups.length+5;
  movement.getRange(`A6:G${end}`).values=d.movement_groups.map(r=>[r.axis,r.speed,r.transition,r.samples,r.mean,r.p95,r.max]);
  movement.getRange(`K6:L${end}`).values=d.movement_groups.map(r=>[r.over_draw,r.over_two_refreshes]);
  movement.getRange('H6:I6').formulas=[['=E6/Sources!$B$4*1000','=G6/Sources!$B$4*1000']];
  movement.getRange(`H6:I${end}`).fillDown();
  movement.getRange(`J6:J${end}`).values=d.movement_groups.map(r=>[d.cpu_hz/r.interval_mean]);
  movement.getRange(`D6:G${end}`).setNumberFormat('#,##0');
  movement.getRange(`H6:J${end}`).setNumberFormat('0.00');
  table(movement,`A5:L${end}`,'MovementCosts');
  movement.getRange('A16').values=[['FPS = clock / mean presentation interval. This does not imply stable cadence or a causal phase-only comparison.']];
  movement.getRange('A17').values=[['Movement follows real keyboard input. Every moving sample is unclamped and its displacement matches elapsed VBlanks.']];
  header(movement,'A20:G20',['Axis','Speed','Camera transition','Frames','World ring cycles','HUD upload cycles','Name table cycles']);
  const rend=d.movement_groups.length+20;
  movement.getRange(`A21:G${rend}`).values=d.movement_groups.map(r=>[r.axis,r.speed,r.transition,r.samples,r.Ring_Prepare,r.hud_upload,r.Ring_UploadNames]);
  movement.getRange(`D21:G${rend}`).setNumberFormat('#,##0');
  table(movement,`A20:G${rend}`,'MovementRoutineCosts');
  movement.getRange('A31').values=[['Selected disjoint child routines, inclusive cycles/frame. Their sum is not the complete rendering cost.']];
  movement.getRange('A32').values=[['Idle includes released-key settling samples and outliers while alternate back tables settle.']];
  header(movement,'A35:G35',['Axis (normal speed)','Fine phase','Frames','Tile crossings','Mean cycles','Mean ms','Max ms']);
  const pend=d.phase_groups.length+35;
  movement.getRange(`A36:E${pend}`).values=d.phase_groups.map(r=>[r.axis,r.phase,r.samples,r.crossings,r.mean]);
  movement.getRange(`G36:G${pend}`).values=d.phase_groups.map(r=>[r.max/d.cpu_hz*1000]);
  movement.getRange('F36').formulas=[['=E36/Sources!$B$4*1000']];
  movement.getRange(`F36:F${pend}`).fillDown();
  movement.getRange(`E36:E${pend}`).setNumberFormat('#,##0');
  movement.getRange(`F36:G${pend}`).setNumberFormat('0.00');
  table(movement,`A35:G${pend}`,'FinePhaseCosts');
  movement.getRange('A53').values=[['Fine phase zero is not equivalent to a crossing: reverse movement can cross from phase 0 to 7.']];
}

title(sources,'Inputs, provenance and acceptance');
header(sources,'A3:B3',['Input','Value']);
sources.getRange('A4:B12').values=[
  ['CPU clock (Hz)',d.cpu_hz],['Current refresh (cycles)',d.cycles_per_refresh],
  ['60 Hz draw interval (cycles)',262*228],['VBlank reserve (cycles)',5000],
  ['Target gameplay FPS',d.target_presented_fps??30],['Current nominal video Hz',50],
  ['Current lines / refresh',313],['CPU clocks / scanline',228],['Target lines / refresh',262]];
sources.getRange('B4:B12').format.font={name:'Arial',size:11,color:blue};
sources.getRange('B4:B12').setNumberFormat('#,##0');
sources.getRange('B8').setNumberFormat('0.00');
sources.getRange('B7').format.fill='#FEF3C7';
sources.getRange('D4').values=[['Clock and scanline model: scripts/msx/inputs.py; ROM selects R9=$82 (50 Hz).']];
sources.getRange('D6').values=[['262 × 228 cycles is the proposed 60 Hz comparison; no 60 Hz gameplay validation yet.']];
sources.getRange('D7').values=[['Interpretation of the user budget: 5,000 cycles; actual usable VBlank deadline remains to be measured.']];
header(sources,'A15:B15',['Measurement','Source / value']);
sources.getRange('A16:B21').values=[['Measured presentations',d.measured_frames],['Machine',d.machine],['Emulator',d.emulator.split('\n')[0]],['ROM SHA-256',d.rom_sha256],['Raw run directory',d.run_path],['Summary JSON',path.resolve(source)]];
sources.getRange('D16').values=[[d.workload]];
sources.getRange('D17').values=[['Contributor ROM; no graphics or original ROM bytes are embedded in this workbook.']];
sources.getRange('D18').values=[['Measured using emulated time × clock, not host wall time or opcode-table estimates.']];
sources.getRange('D19').values=[['clock_irq measures ISR body through RETI; hardware entry and vector jump are excluded from its row.']];
sources.getRange('D20').values=[['calls.tsv records every call; frames.tsv and control-frames.tsv retain independent frame observations.']];
sources.getRange('D21').values=[['profile.py asserts nested-cost reconciliation, complete routine coverage and control-run agreement.']];
sources.getRange('A24').values=[['Acceptance rules']];
sources.getRange('D24:D28').values=[
  ['Performance priority: approach 30 FPS with measured worst-case margins.'],
  ['User has final acceptance of every graphical or perceptual concession.'],
  [d.layout?.left_mask_required===8
    ? 'SCREEN 4, right-edge simplification and fixed 8-pixel left mask are approved only for this laboratory.'
    : 'Existing SCREEN 4 and right-edge simplifications are approved only for the laboratory.'],
  ['Flag pauses are scheduling candidates; define event duration, bounded work and resume behavior.'],
  ['No physical hardware test; production AI, sound and flag capture are outside this workload.']];
if (d.layout?.round_label==='RND') {
  sources.getRange('D29').values=[['Footer: RND <=99, scores <=999999, up to four complete native cars. Laboratory build inputs only.']];
  sources.getRange('D29').format.font={name:'Arial',size:10,color:gray};
}
// Keep long provenance strings in separate full-width rows so hash/path text
// does not collide with the visible notes column.
for (const row of [19,20,21]) {
  const value=sources.getRange(`B${row}`).values[0][0];
  sources.getRange(`B${row}`).values=[['See row '+(row+11)]];
  sources.getRange(`A${row+11}`).values=[[String(value)]];
}
sources.getRange('A30:A32').format.font={name:'Arial',size:9,color:gray};
if (comparison) {
  const c=d.optimization_comparison;
  setup(comparison,'J36',[28,21,21,18,19,19,19,19,19,19]);
  title(comparison,'Further optimization: same graphics');
  comparison.getRange('A3').values=[[actionOnly?'Three-enemy action only; same keyboard policy, both interval endpoints active; cadence changes sampling and outcomes.':'Same keyboard controller policy, ten flags and one death; cadence changes sampling and input feedback timing.']];
  header(comparison,'A5:D5',['Metric','Before','After','Change']);
  comparison.getRange('A6:C11').values=[
    [actionOnly?'Active profile FPS':'Full-route profile FPS',c.baseline.fps,c.current.fps],
    [actionOnly?'Active verification FPS':'Active movement FPS',c.baseline_active.fps,c.current_active.fps],
    ['Mean active work ms',c.baseline.work_mean_ms,c.current.work_mean_ms],
    ['P95 presentation ms',c.baseline.interval_p95_ms,c.current.interval_p95_ms],
    ['Maximum interval ms',c.baseline.interval_max_ms,c.current.interval_max_ms],
    ['Intervals <=33.6 ms %',c.baseline.within_two_refreshes_percent,c.current.within_two_refreshes_percent]];
  comparison.getRange('D6').formulas=[['=C6/B6-1']];
  comparison.getRange('D6:D11').fillDown();
  comparison.getRange('B6:C11').setNumberFormat('0.00');
  comparison.getRange('D6:D11').setNumberFormat('0.0%');
  const selected=['Ring_UploadNames','Ring_Prepare','Game_Radar','Game_LogicTick','Game_Position','GameSprites_Prepare','Game_Prepare','render'];
  header(comparison,'A14:J14',['Routine','Before mean incl.','After mean incl.','Saved cycles/call','Before P95','After P95','Before max','After max','Before calls/frame','After calls/frame']);
  comparison.getRange('A15:C22').values=selected.map(name=>[name,c.baseline_routines.find(r=>r.name===name).mean,d.routines.find(r=>r.name===name).mean]);
  comparison.getRange('D15').formulas=[['=B15-C15']];
  comparison.getRange('D15:D22').fillDown();
  comparison.getRange('E15:J22').values=selected.map(name=>{const b=c.baseline_routines.find(r=>r.name===name),a=d.routines.find(r=>r.name===name);return[b.p95,a.p95,b.max,a.max,b.calls_per_frame,a.calls_per_frame]});
  comparison.getRange('B15:H22').setNumberFormat('#,##0');
  comparison.getRange('I15:J22').setNumberFormat('0.00');
  table(comparison,'A14:J22','OptimizationCosts');
  comparison.getRange('A24').values=[['Inclusive parent/child rows overlap; never sum them. Per-presentation work changes with cadence.']];
  comparison.getRange('A25').values=[['Active FPS excludes death hold, all-flags bonus and stopped state at both interval endpoints.']];
  comparison.getRange('A27').values=[['Graphics: seven terrain/palette/car/font/life/base-HUD payloads are byte-identical to baseline.']];
  comparison.getRange('A28').values=[['All 64 fine phases and all 1024 flag masks preserve exact radar pixels in independent synthetic tests.']];
  comparison.getRange('A29').values=[['The native hardware sprite limit, original complete car masks and VBlank publication remain enabled.']];
  comparison.getRange('A31').values=[['Loop residual includes standalone ISR bodies; routine-self reconciliation uses only untracked loop overhead.']];
  comparison.getRange('A33').values=[['Worst observed interval: '+c.current.interval_max_ms.toFixed(2)+' ms; no artificial pause or new graphical reduction.']];
  comparison.getRange('A35').values=[['Baseline ROM SHA-256: '+c.baseline_rom_sha256]];
  comparison.getRange('A36').values=[['Current ROM SHA-256: '+d.rom_sha256]];
  comparison.getRange('A24:A36').format.font={name:'Arial',size:10,color:gray};
}
if (multi) {
  setup(multi,'L34',[17,18,19,19,17,19,18,18,20,19,22,24]);
  title(multi,'Real multi-enemy workloads');
  multi.getRange('A3').values=[['Original AI and complete car graphics; explicit test spawns. HUD/audio and real eight-sprite limit enabled.']];
  header(multi,'A5:L5',['Enemies','Samples','Peak visible','Enemies moved','Active smoke FPS','Route FPS','Active route FPS','Max sprites/line','Overflow frames','Overflow lines','Whole-car cull frames','Route outcome']);
  multi.getRange('A6:L7').values=d.multi_car_workloads.map(v=>{
    const p=v.population;return[v.enemies,p.samples,p.maximum_simultaneously_visible_enemies,p.moved_enemies,
      v.active_smoke?.fps??v.smoke.presented_fps,v.route?.presented_fps??null,v.active?.fps??null,
      p.maximum_scanline_sprite_candidates,p.frames_with_hardware_scanline_overflow,
      p.scanlines_with_hardware_overflow,p.sentinel_whole_car_cull_frames,
      v.route?(v.route.stage_completed?'Completed':'Native game over'):'Smoke stress only'];
  });
  multi.getRange('E6:G7').setNumberFormat('0.00');
  header(multi,'A10:E10',['Three-enemy profile','Before','After','Unit','Scope']);
  const v=d.multi_car_workloads.find(v=>v.enemies===3);
  multi.getRange('A11:E13').values=[['Presentation rate',v.baseline.fps,v.profile.fps,'FPS','Until native game over'],
    ['Mean work',v.baseline.work_mean_ms,v.profile.work_mean_ms,'ms','Excludes sync waits'],
    ['Max interval',v.baseline.interval_max_ms,v.profile.interval_max_ms,'ms','Includes holds and heavy frames']];
  multi.getRange('B11:C13').setNumberFormat('0.00');
  multi.getRange('A16').values=[['Visible/movement and hardware-pressure counts come from a separate 480-frame keyboard + smoke population trace.']];
  multi.getRange('A17').values=[['Active smoke FPS uses another 480-frame four-direction route; death/bonus/stopped excluded at both interval endpoints.']];
  multi.getRange('A18').values=[['Three-enemy full navigation ended after native lives expired. No lives/positions were injected; it did not complete the stage.']];
  multi.getRange('A19').values=[['Seven-enemy stress falls below 30 FPS and can lose sprite lines through the authentic hardware limit.']];
  multi.getRange('A20').values=[['Prepared visible cars and actual hardware-displayed lines are distinct. Overflow is recorded, not disabled.']];
  d.multi_car_workloads.forEach((v,i)=>{
    multi.getRange(`A${23+i*3}`).values=[[`${v.enemies}-enemy ROM SHA256: ${v.rom_sha256}`]];
    multi.getRange(`A${24+i*3}`).values=[[v.population_path]];
    multi.getRange(`A${25+i*3}`).values=[[v.smoke_path]];
  });
  multi.getRange('A29').values=[[d.evidence_scope]];
  multi.getRange('A16:A29').format.font={name:'Arial',size:10,color:gray};
  if(actionOnly){
    multi.getRange('A14:E14').values=[['Active verification FPS',d.optimization_comparison.baseline_active.fps,v.active.fps,'FPS','Death/bonus/stopped excluded']];
    multi.getRange('B14:C14').setNumberFormat('0.00');
  }
  const costs=v.active_profile?.routines??v.routines,last=costs.length+5;
  setup(multiCosts,`L${last+5}`,[25,42,12,12,15,15,15,15,15,17,15,17]);
  title(multiCosts,'Three-enemy action costs');
  multiCosts.getRange('A3').values=[['Both endpoints active; death/bonus/stopped excluded. Inclusive parents overlap children; no seven-enemy profile implied.']];
  header(multiCosts,'A5:L5',['Routine / hook','Purpose','Calls','Calls/frame','Min incl.','Mean incl.','P95 incl.','Max incl.','Mean self','Self / frame','Mean incl. ms','Self/frame % refresh']);
  const count=costs.find(r=>r.name==='Game_Prepare').calls;
  multiCosts.getRange(`A6:J${last}`).values=costs.map(r=>[r.name,r.purpose,r.calls,r.calls_per_frame,r.min,r.mean,r.p95,r.max,r.self_mean,r.self_total/count]);
  multiCosts.getRange('K6:L6').formulas=[['=F6/Sources!$B$4*1000','=J6/Sources!$B$5']];
  multiCosts.getRange(`K6:L${last}`).fillDown();
  costs.forEach((r,i)=>{if(!r.calls)multiCosts.getRange(`K${i+6}`).values=[[null]];});
  multiCosts.getRange(`C6:J${last}`).setNumberFormat('#,##0');
  multiCosts.getRange(`D6:D${last}`).setNumberFormat('0.00');
  multiCosts.getRange(`K6:K${last}`).setNumberFormat('0.000');
  multiCosts.getRange(`L6:L${last}`).setNumberFormat('0.0%');
  table(multiCosts,`A5:L${last}`,'ThreeEnemyRoutineCosts');
  multiCosts.getRange(`A${last+2}`).values=[['ROM SHA256: '+v.rom_sha256]];
  multiCosts.getRange(`A${last+3}`).values=[[v.profile_path]];
}
if (cache) {
  setup(cache,'I31',[36,18,18,18,18,18,18,18,18]);
  title(cache,'Smoke candidate-row cache: isolated CPU costs');
  cache.getRange('A3').values=[[`${d.synthetic_smoke_cache.cases} differential assembled Z80 cases; ordered sparse output matches original full scan.`]];
  header(cache,'A5:G5',['Workload','Calls','Original mean','Candidate mean','Original max','Candidate max','Saved mean cycles']);
  const rows=Object.entries(d.synthetic_smoke_cache.workloads).filter(([,v])=>v.baseline&&v.candidate).map(([name,v])=>
    [name,v.candidate.calls,v.baseline.mean,v.candidate.mean,v.baseline.maximum,v.candidate.maximum,v.baseline.mean-v.candidate.mean]);
  cache.getRange(`A6:G${rows.length+5}`).values=rows;
  cache.getRange(`B6:G${rows.length+5}`).setNumberFormat('#,##0');
  cache.getRange('A23').values=[['Inclusive entry-to-return cycles, no IRQ/synchronization. Marker hook costs remain in the JSON ledger.']];
  cache.getRange('A24').values=[['Native ring bytes and output order are exact; dense rows have a small bookkeeping overhead.']];
  cache.getRange('A25').values=[['Do not add this helper to its Game_RingPatch parent cost. Integrated calls are cadence/workload dependent.']];
  cache.getRange('A27').values=[['Probe ROM SHA256: '+d.synthetic_smoke_cache.rom_sha256]];
  cache.getRange('A28').values=[['Helper source SHA256: '+d.synthetic_smoke_cache.source_sha256]];
  cache.getRange('A23:A28').format.font={name:'Arial',size:10,color:gray};
}
if (dirty) {
  const t=d.synthetic_dirty_names;
  const rows=Object.entries(t.workloads).map(([key,v])=>[key,v.GameDirty_Plan.mean,v.Ring_UploadNames.mean,
    v.GameDirty_Upload.mean,v.baseline_full_Ring_UploadNames.mean,v.dirty_data_writes.mean]);
  setup(dirty,`I${rows.length+13}`,[37,21,22,22,24,24,18,18,18]);
  title(dirty,'Changed-cell name publication');
  dirty.getRange('A3').values=[[`${t.cases} cases, ${t.phases} back-buffer phases, ${t.marker_calls} mark calls; byte-exact RAM/VRAM checks.`]];
  header(dirty,'A5:G5',['Workload','Plan mean','Ring mean','Dirty upload mean','Full-refill mean','Dirty VRAM bytes','Total saved cycles']);
  dirty.getRange(`A6:F${rows.length+5}`).values=rows;
  dirty.getRange('G6').formulas=[['=E6-B6-C6-D6']];
  dirty.getRange(`G6:G${rows.length+5}`).fillDown();
  dirty.getRange(`B6:G${rows.length+5}`).setNumberFormat('#,##0');
  const row=rows.length+8;
  dirty.getRange(`A${row}`).values=[['Disjoint plan + ring + upload can be summed here; Mark runs during the parent patch and is listed separately in JSON.']];
  dirty.getRange(`A${row+1}`).values=[['24+ dirty groups use full sequential refill; no duplicate dirty upload. 23 scattered groups can cost more than a refill.']];
  dirty.getRange(`A${row+2}`).values=[['Synthetic worst cases are not native workload rates; full-page data, all wraps, duplicate marks and both buffers are checked.']];
  dirty.getRange(`A${row+3}`).values=[['Probe ROM SHA256: '+t.rom_sha256]];
}
// Formula cells remain dark; notes use a lighter but legible tone.
budget.getRange('F6:F25').format.font={name:'Arial',size:10,color:gray};
sources.getRange('D4:D28').format.font={name:'Arial',size:10,color:gray};
if (d.frames[0]?.Game_Prepare !== undefined) {
  const approvedEffects=!!d.effect_adaptation;
  title(budget,actionOnly?'Three-enemy action cycle budget':approvedEffects?'First-stage cycle budget':'First-stage integration fixture cycle budget');
  budget.getRange('A3').values=[[`${d.measured_frames} ${actionOnly?'active ':''}presentations; 60 Hz refresh; ${approvedEffects?"authorized native effects":"SYNTHETIC EFFECTS, graphics decision pending"}`]];
  budget.getRange('A14').values=[['Current 60 Hz video refresh']];
  budget.getRange('F7').values=[['Cadence varies with work; average FPS is not stable FPS. Inspect tails and event intervals.']];
  budget.getRange('F15').values=[['This integration fixture selects R9=$80 and nominal 60 Hz refresh.']];
  budget.getRange('F25').values=[[approvedEffects?'Smoke/explosion adaptation authorized 2026-10-28 only in this experiment; final visual acceptance pending.':'Only synthetic effect tiles are used; new original-effect reductions await user approval.']];
  budget.getRange('A28').values=[[actionOnly?'Scope: three real enemies during action; HUD, PSG, smoke and native logic; death/bonus/stopped intervals excluded.':approvedEffects?'Scope: moving first-stage route, native logic, enemies, HUD, PSG and authorized native effects.':'Scope: moving first-stage route, native logic, enemies, HUD and PSG; synthetic effects.']];
  budget.getRange('A29').values=[[d.control_check]];
  frames.getRange('F5').values=[['Simulation + actor/HUD preparation cycles']];
  frames.getRange('F5').format.wrapText=true;
  sources.getRange('B9:B10').values=[[60],[262]];
  sources.getRange('D4').values=[['Guest CPU 3,579,545 Hz; R9=$80; 262 lines x228 cycles. Refresh and presentation are distinct.']];
  sources.getRange('D6').values=[['One refresh 59,736 cycles; two 119,472. Full-frame work differs from usable VBlank.']];
  sources.getRange('D17').values=[[approvedEffects?'Native 24x24 effects: explosion 23/576 pixels and smoke 37/576 pixels changed by the authorized row codec.':'Link/test fixture with synthetic effect tiles; original-effect gameplay ROM is not accepted.']];
  sources.getRange('D28').values=[['No physical hardware validation; moving-route performance is preliminary and scoped.']];
  sources.getRange('D29').values=[['Live native HUD values saturate their display only: RND 99, scores 999999, four extra-life icons.']];
  const scenarioNote=(d.separate_scenarios??[]).map(s=>`${s.scenario}: ${s.presented_fps.toFixed(2)} FPS over ${s.frames} presentations`).join('; ');
  budget.getRange('F28').values=[[scenarioNote||'Heavy/smoke workloads are not measured by this route.']];
  budget.getRange('F29').values=[['Separate workload observations; no stable 30 FPS or accepted event-pause claim.']];
  budget.getRange('F28').format.wrapText=true;
  budget.getRange('F28').format.rowHeight=45;
  budget.getRange('F29').values=[['Separate workloads include death/bonus holds; do not compare these FPS as a causal optimization test.']];
  budget.getRange('F28:F29').format.font={name:'Arial',size:10,color:gray};
  if(actionOnly){
    budget.getRange('F29').values=[['Primary budget and routine tables exclude holds. MultiCar retains separate whole-route/smoke observations.']];
    sources.getRange('D16').values=[[d.workload]];
  }

}
if(d.target_presented_fps){
  const goal=d.target_presented_fps.toFixed(2);
  budget.getRange('A11').values=[['Work over '+goal+' FPS budget']];
  budget.getRange('A20').values=[['Mean work: '+goal+' FPS remaining budget']];
  budget.getRange('F18').values=[['Nominal '+goal+' FPS target; actual two-refresh cadence follows the measured video clock.']];
  sources.getRange('D8').values=[['Nominal NTSC target '+goal+' FPS; measured two-refresh cadence '+(d.cpu_hz/(2*d.cycles_per_refresh)).toFixed(6)+' FPS.']];
  sources.getRange('D24').values=[['Performance priority: approach '+goal+' FPS through the measured presenter + logic critical path.']];
}
wb.recalculate();
const previews=[['Budget','A1:F30'],['Routines',`A1:L${nr+4}`],['Frames','A1:U18'],['Sources','A1:D32']];
if (movement) previews.push(['Movement','A1:L53']);
if (comparison) previews.push(['Optimization','A1:J36']);
if (multi) previews.push(['MultiCar','A1:L29']);
if (multiCosts) previews.push(['MultiCarCosts',`A1:L${d.multi_car_workloads.find(v=>v.enemies===3).routines.length+8}`]);
if (cache) previews.push(['SmokeCache','A1:I28']);
if (dirty) previews.push(['DirtyNames',`A1:I${Object.keys(d.synthetic_dirty_names.workloads).length+11}`]);
for (const [sheetName,range] of previews) {
  const blob=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(outputDir,sheetName.toLowerCase()+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const inspection=await wb.inspect({kind:'region',sheetId:'Budget',range:'A5:D19',maxChars:3000,tableMaxRows:16,tableMaxCols:4});
await fs.writeFile(path.join(outputDir,'inspection.json'),JSON.stringify(inspection,null,2));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'Final formula error scan'});
await fs.writeFile(path.join(outputDir,'formula-errors.json'),JSON.stringify(errors,null,2));
const file=await SpreadsheetFile.exportXlsx(wb);
await file.save(path.join(outputDir,'cycle-budget.xlsx'));
console.log(path.join(outputDir,'cycle-budget.xlsx'));
