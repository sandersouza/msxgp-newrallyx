"""Exact scanline deadlines and fail-closed physical/queue evidence."""
import csv
import json
import math
from pathlib import Path


def deadline_state(n: int, lines: int) -> tuple[int,int,int,int]:
    if type(n) is not int or n < 0 or type(lines) is not int or lines not in (313,262):
        raise ValueError('Invalid deadline index/frame timing')
    total = n*259+(n*1399+30399)//30400
    line = total%lines
    error = (-n*1399)%30400
    target = line if line <= 212 else 0
    actual = total if line <= 212 else total+lines-line
    return line,error,target,actual


def analyze_deadline_math(output: Path, lines: int) -> dict:
    line,error,_,_ = deadline_state(100000,lines)
    expected = dict(cases=100000,frame_lines=lines,deadline=line,error=error)
    actual = json.loads((output/'fine-math.json').read_text())
    if (actual != expected or not isinstance(actual,dict)
            or any(type(v) is not int for v in actual.values())):
        raise ValueError('Invalid deadline arithmetic proof')
    return actual


def analyze_deadlines(output: Path, lines: int, count: int) -> dict:
    deadline_state(0,lines)
    if type(count) is not int or count < 1:
        raise ValueError('Invalid deadline acquisition length')
    with (output/'fine.tsv').open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    fields = {'event','sequence','line','error','target','claimed','pending','accepted','armed','time'}
    start = previous_time = None
    previous_accepted = previous_claimed = previous_armed = max_pending = 0
    max_delay = 0.0
    try:
        if len(rows) < 2:
            raise ValueError('Incomplete deadline samples')
        for n,row in enumerate(rows):
            if set(row) != fields:
                raise ValueError('Wrong deadline sample fields')
            values = {k:int(row[k]) for k in fields-{'event','time'}}
            time = float(row['time'])
            line,error,target,physical = deadline_state(n,lines)
            if (row['event'] != ('sync' if n == 0 else 'deadline') or values['sequence'] != n
                    or (values['line'],values['error'],values['target']) != (line,error,target)
                    or not math.isfinite(time) or time < 0
                    or not previous_claimed <= values['claimed'] <= count
                    or not 0 <= values['pending'] <= 0xffffffff
                    or values['claimed']+values['pending'] != values['accepted']
                    or not previous_accepted <= values['accepted'] <= previous_accepted+1
                    or values['armed'] not in (0,1) or values['armed'] < previous_armed
                    or bool(values['accepted']) != bool(values['armed'])):
                raise ValueError('Deadline phase or queue conservation changed')
            if n == 0:
                if values['accepted'] or values['armed']:
                    raise ValueError('Deadline clock did not start unarmed')
                start = time
            else:
                delay = abs((time-start)*3579545-physical*228)
                if (time <= previous_time or delay > 4096
                        or (values['armed'] and values['accepted'] != previous_accepted+1)):
                    raise ValueError('Lost or mistimed deadline')
                max_delay = max(max_delay,delay)
            previous_time = time
            previous_accepted,previous_claimed,previous_armed = (values[k] for k in ('accepted','claimed','armed'))
            max_pending = max(max_pending,values['pending'])
        final = json.loads((output/'fine-final.json').read_text())
        if (not isinstance(final,dict) or set(final) != {'claimed','pending','accepted','deadlines'}
                or any(type(v) is not int for v in final.values())
                or final['claimed'] != count or not 0 <= final['pending'] <= 0xffffffff
                or final['claimed']+final['pending'] != final['accepted']
                or final['accepted'] != previous_accepted+1 or final['deadlines'] != len(rows)-1):
            raise ValueError('Final deadline state is inconsistent')
    except (KeyError,TypeError,ValueError) as error:
        raise ValueError('Invalid deadline execution evidence') from error
    return dict(deadlines=len(rows)-1,accepted=final['accepted'],
                max_pending=max(max_pending,final['pending']),final_pending=final['pending'],
                max_phase_delay_difference_cycles=max_delay)
