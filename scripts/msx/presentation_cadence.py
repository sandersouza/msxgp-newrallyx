"""Measure complete presentation commits without bridging inactive states."""
from collections import Counter,defaultdict
import math


def analyze(path,frame_seconds):
    rounds=defaultdict(lambda:dict(gaps=[],work=[]))
    previous=start=None
    for line in path.read_text().splitlines():
        time,round_,kind,tick,*state=line.split()
        time=float(time);round_=int(round_)
        if len(state)!=4 or kind not in ('start','ready','commit'):
            raise ValueError('Unexpected presentation sample')
        if any(int(v) for v in state):
            previous=start=None
            continue
        if kind=='start':start=(round_,time)
        elif kind=='ready':
            if start and start[0]==round_:
                rounds[round_]['work'].append(time-start[1])
            start=None
        elif kind=='commit':
            if previous and previous[0]==round_:
                elapsed=time-previous[1]
                if elapsed<=0:raise ValueError('Presentation time did not advance')
                rounds[round_]['gaps'].append(elapsed)
            previous=(round_,time)
    result=[]
    for round_,data in sorted(rounds.items()):
        gaps=data['gaps'];work=data['work']
        if not gaps:continue
        def p95(values):
            ordered=sorted(values)
            return ordered[math.ceil(.95*len(ordered))-1]*1000 if ordered else None
        result.append(dict(displayed_round=round_-1,intervals=len(gaps),
            commit_hz=len(gaps)/sum(gaps),maximum_gap_ms=max(gaps)*1000,
            percentile_95_gap_ms=p95(gaps),percentile_95_work_ms=p95(work),
            missed_slots_percent=sum(g>frame_seconds*3 for g in gaps)*100/len(gaps),
            intervals_in_refreshes=dict(sorted(Counter(round(g/frame_seconds) for g in gaps).items()))))
    if not result:raise ValueError('Missing active presentation commits')
    return dict(rounds=result,target_hz=1/(2*frame_seconds),
        scope='Complete VBlank packet commits. Inactive start/ready/commit observations split segments; active stalls remain included. Work ends at sealing; hidden idle prefetch does not alter the packet.')
