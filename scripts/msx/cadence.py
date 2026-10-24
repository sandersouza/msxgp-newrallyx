"""Measure native simulation time separately from foreground presentation loops."""
from collections import defaultdict
import math


def analyze(path):
    rows=[]
    for line in path.read_text().splitlines():
        values=line.split()
        if len(values) not in (10,12):
            raise ValueError('Unexpected cadence sample width')
        row=[float(values[0]),*map(int,values[1:])]
        if not math.isfinite(row[0]):raise ValueError('Invalid cadence time')
        rows.append(row)
    rounds=defaultdict(list)
    for old,new in zip(rows,rows[1:]):
        elapsed=new[0]-old[0]
        if elapsed<=0:raise ValueError('Cadence time did not advance')
        # Loading, death and completion are reported by their own state gates.
        # Long active stalls remain in the denominator; never discard them.
        if old[1]!=new[1] or old[2:4]!=[0,0] or new[2:4]!=[0,0]:continue
        ticks=(new[4]-old[4])&65535
        holds=(new[5]-old[5])&65535
        if ticks>7 or holds>1:raise ValueError('Native cadence counter discontinuity')
        dropped=((new[10]-old[10])&65535) if len(new)==12 else None
        rounds[old[1]].append(dict(start=old[0],end=new[0],ticks=ticks,held=holds,
            dropped=dropped,enemies=old[6],debt=old[8] if len(old)==12 else None))
    result=[]
    for internal,samples in sorted(rounds.items()):
        seconds=sum(s['end']-s['start'] for s in samples)
        ticks=sum(s['ticks'] for s in samples)
        run=longest=0
        for s in samples:
            run=run+s['end']-s['start'] if s['held'] else 0
            longest=max(longest,run)
        # Integrate ticks uniformly over each observed loop. Complete five
        # second windows reveal sustained slowness without presentation jitter.
        windows=defaultdict(lambda:[0.,0.])
        origin=samples[0]['start']
        for s in samples:
            first=int((s['start']-origin)//5);last=int((s['end']-origin)//5)
            duration=s['end']-s['start']
            for n in range(first,last+1):
                overlap=max(0.,min(s['end'],origin+(n+1)*5)-max(s['start'],origin+n*5))
                windows[n][0]+=overlap
                windows[n][1]+=s['ticks']*overlap/duration
        rates=[t/d for d,t in windows.values() if d>=4.99]
        result.append(dict(displayed_round=internal-1,internal_round=internal,
            active_seconds=seconds,native_ticks=ticks,native_hz=ticks/seconds,
            foreground_loops=len(samples),presentation_loop_hz=len(samples)/seconds,
            maximum_loop_ms=max(s['end']-s['start'] for s in samples)*1000,
            held_loops=sum(s['held'] for s in samples),longest_hold_ms=longest*1000,
            minimum_five_second_native_hz=min(rates) if rates else None,
            enemy_counts=sorted({s['enemies'] for s in samples}),
            discarded_ticks=sum(s['dropped'] for s in samples) if samples[0]['dropped'] is not None else None,
            maximum_clock_debt=max(s['debt'] for s in samples) if samples[0]['debt'] is not None else None))
    if not result:raise ValueError('Missing active native cadence samples')
    return dict(rounds=result,original_native_hz=1/.0165,
        scope='Emulated elapsed time and native tick counters during consecutive active samples; foreground loops are not physical refreshes. Active stalls remain included.')
