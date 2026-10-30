"""Keep audio call costs exclusive of measured children and raster IRQ time."""
from collections import defaultdict
from math import ceil


def summarize(path, presentation_path, frame_seconds):
    costs=defaultdict(lambda:[0.,0.,0])
    children=defaultdict(float)
    for line in path.read_text().splitlines():
        name,parent,frame,wall,cpu=line.split();key=(int(frame),name)
        values=costs[key];values[0]+=float(wall);values[1]+=float(cpu);values[2]+=1
        children[(int(frame),parent)]+=float(cpu)
    grouped=defaultdict(list)
    for (frame,name),(wall,cpu,count) in costs.items():
        own=cpu-children[(frame,name)]
        if own < -.01:raise ValueError(f'Audio cycle accounting double-counted children: {name}, {frame}')
        grouped[name].append((wall,cpu,max(0.,own),count))
    commits=sum(line.split()[2]=='commit' for line in presentation_path.read_text().splitlines())
    rows=[]
    for name,values in sorted(grouped.items()):
        cpu=sorted(v[1] for v in values);wall=sorted(v[0] for v in values);own=sorted(v[2] for v in values)
        rows.append(dict(routine=name,calls=sum(v[3] for v in values),
            calls_per_presented_packet=sum(v[3] for v in values)/commits,
            mean_inclusive_cycles=sum(wall)/len(wall),p95_inclusive_cycles=wall[ceil(len(wall)*.95)-1],
            maximum_inclusive_cycles=max(wall),mean_cpu_cycles=sum(cpu)/len(cpu),
            mean_self_cycles=sum(own)/len(own),p95_self_cycles=own[ceil(len(own)*.95)-1],maximum_self_cycles=max(own)))
    budget=3579545*frame_seconds*2
    root=next(r for r in rows if r['routine']=='Audio_Work')
    return dict(routines=rows,base_equivalent_hz=3579545,physical_refresh_seconds=frame_seconds,
        routine_cost_basis='Totals per foreground loop containing this routine; repeated helper calls in that loop are grouped.',
        physical_refresh_budget_cycles=budget/2,presentation_packet_budget_cycles=budget,
        mean_budget_after_audio_only=budget-root['mean_cpu_cycles']*root['calls_per_presented_packet'],
        vblank_budget_cycles=None,
        scope='3.58 MHz equivalent elapsed cycles under factory CPU switching, not raw turbo instruction counts. '
              'Inclusive time contains raster IRQs; CPU excludes observed IRQs. Self subtracts instrumented direct '
              'audio calls; platform helpers and tail jumps remain in their caller. Per-frame sums support multiple '
              'calls; never add inclusive parent and child rows. Remaining budget subtracts audio only, not rendering. '
              'No usable VBlank reserve is inferred from this ledger.')
