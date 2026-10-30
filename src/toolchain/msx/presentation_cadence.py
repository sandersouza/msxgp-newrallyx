"""Measure complete presentation commits without bridging inactive states."""
from collections import Counter,defaultdict
from bisect import bisect_right
import math


def analyze(path,frame_seconds,population_path=None):
    rounds=defaultdict(lambda:dict(gaps=[],work=[]))
    populations=defaultdict(lambda:dict(gaps=[],work=[]))
    samples=([list(map(float,line.split())) for line in population_path.read_text().splitlines()]
             if population_path is not None else [])
    if any(len(row) not in (10,12,13) for row in samples):raise ValueError('Unexpected population sample')
    times=[row[0] for row in samples]
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Population time did not advance')
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
            index=bisect_right(times,time)-1
            sample=samples[index] if index>=0 else None
            count=(int(sample[6]) if sample and sample[1]==round_ and
                   sample[2:4]==[0,0] else None)
            if previous and previous[0]==round_:
                elapsed=time-previous[1]
                if elapsed<=0:raise ValueError('Presentation time did not advance')
                rounds[round_]['gaps'].append(elapsed)
                if count is not None and previous[2]==count:
                    populations[(round_,count)]['gaps'].append(elapsed)
            previous=(round_,time,count)
    def summarize(round_,data):
        gaps=data['gaps'];work=data['work']
        if not gaps:return None
        def p95(values):
            ordered=sorted(values)
            return ordered[math.ceil(.95*len(ordered))-1]*1000 if ordered else None
        return dict(displayed_round=round_-1,intervals=len(gaps),active_seconds=sum(gaps),
            commit_hz=len(gaps)/sum(gaps),maximum_gap_ms=max(gaps)*1000,
            percentile_95_gap_ms=p95(gaps),percentile_95_work_ms=p95(work),
            missed_slots_percent=sum(g>frame_seconds*2.5 for g in gaps)*100/len(gaps),
            intervals_in_refreshes=dict(sorted(Counter(round(g/frame_seconds) for g in gaps).items())))
    result=[summary for r,data in sorted(rounds.items()) if (summary:=summarize(r,data))]
    population_results=[]
    for (round_,count),data in sorted(populations.items()):
        summary=summarize(round_,data)
        if summary:population_results.append(dict(summary,enemy_count=count))
    if not result:raise ValueError('Missing active presentation commits')
    return dict(rounds=result,populations=population_results,target_hz=1/(2*frame_seconds),
        population_scope='Commit intervals joined to the most recent active foreground population sample in the same round; population changes break intervals. Active stalls remain included.',
        scope='Complete VBlank packet commits. Inactive start/ready/commit observations split segments; active stalls remain included. Work ends at sealing; hidden idle prefetch does not alter the packet.')
