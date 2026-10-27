"""Observe actual physical camera latches, including unpaid movement debt."""
from collections import Counter
import math


def analyze(path,frame_seconds):
    rows=[list(map(float,line.split())) for line in path.read_text().splitlines()]
    if any(len(row)!=18 for row in rows):raise ValueError('Unexpected physical motion sample width')
    result=[]
    for round_ in sorted({int(row[1]) for row in rows}):
        for axis,name,column,pending,centre,blocked in ((255,'horizontal',4,6,124,1),(0,'vertical',5,7,105,2)):
            seconds=frames=updates=run=longest=owed_run=longest_owed=maximum_step=0
            last_update=None;gaps=[]
            for old,new in zip(rows,rows[1:]):
                dt=new[0]-old[0]
                eligible=(old[1]==new[1]==round_ and old[2:4]==new[2:4]==[0,0]
                    and old[13:18]==new[13:18]==[0]*5 and old[8]==new[8]==axis
                    and old[10]>0 and new[10]>0 and old[11]==new[11]==0
                    and not(int(old[9])&blocked) and not(int(new[9])&blocked)
                    and 0<dt<frame_seconds*1.5)
                if not eligible:run=owed_run=0;last_update=None;continue
                frames+=1;seconds+=dt;step=abs(new[column]-old[column]);maximum_step=max(maximum_step,step)
                if step:
                    updates+=1;run=owed_run=0
                    if last_update is not None:gaps.append(new[0]-last_update)
                    last_update=new[0]
                else:
                    run+=1;longest=max(longest,run)
                    if abs(new[pending]-(new[column]+centre))>1:
                        owed_run+=1;longest_owed=max(longest_owed,owed_run)
                    else:owed_run=0
            if not frames:continue
            ordered=sorted(gaps)
            result.append(dict(displayed_round=round_-1,axis=name,eligible_refreshes=frames,
                seconds=seconds,changed_refreshes=updates,update_hz=updates/seconds,
                repeated_percentage=(frames-updates)*100/frames,maximum_step_pixels=maximum_step,
                maximum_repeat_ms=longest*frame_seconds*1000,
                maximum_owed_repeat_ms=longest_owed*frame_seconds*1000,
                percentile_95_update_interval_ms=ordered[math.ceil(.95*len(ordered))-1]*1000 if ordered else None,
                update_intervals_in_refreshes=dict(sorted(Counter(round(g/frame_seconds) for g in gaps).items()))))
    if not result:raise ValueError('Missing eligible physical camera samples')
    return dict(rounds=result,scope='Actual X/Y maze latches during active unblocked native forward motion; excludes loading, pause, fuel conversion, death and round transitions. Owed repeats require more than one pixel between native pending centre and the actual displayed centre. Legitimate wall stops can remain in the broader repeat count.')
