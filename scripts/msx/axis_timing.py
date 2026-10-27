"""Compare simulation and score clocks during sustained movement on each axis."""
from bisect import bisect_left, bisect_right
from collections import defaultdict


def analyze(motion_path, audio_path, presentation_path=None):
    motion = [list(map(float, line.split())) for line in motion_path.read_text().splitlines()]
    audio = [list(map(float, line.split())) for line in audio_path.read_text().splitlines()]
    times = [r[0] for r in audio]
    commits = ([float(r[0]) for line in presentation_path.read_text().splitlines()
                if (r := line.split())[2] == 'commit'] if presentation_path else [])
    totals = defaultdict(lambda: dict(seconds=0., ticks=0, audio_seconds=0., score_frames=0,
                                     display_seconds=0., display_intervals=0, segments=0))
    segment = []

    def flush():
        if len(segment) < 2: return
        first, last = segment[0], segment[-1]
        seconds = last[0]-first[0]
        if seconds < .5: return
        axis = 'horizontal' if first[8] == 255 else 'vertical'
        values = totals[axis]
        values['seconds'] += seconds
        values['ticks'] += (int(last[12])-int(first[12])) & 65535
        values['segments'] += 1
        samples = audio[bisect_left(times, first[0]):bisect_right(times, last[0])]
        if len(samples) >= 2:
            values['audio_seconds'] += samples[-1][0]-samples[0][0]
            values['score_frames'] += sum(int(r[2]) for r in samples[1:])
        frames = commits[bisect_left(commits, first[0]):bisect_right(commits, last[0])]
        if len(frames) >= 2:
            values['display_seconds'] += frames[-1]-frames[0]
            values['display_intervals'] += len(frames)-1

    for row in motion:
        # Death/completion/loading/UI/pause are separate clocks. Keep stopped
        # physical frames within a stable direction/speed run in the denominator.
        speed = (int(row[10])+32768) % 65536-32768
        valid = not any(row[i] for i in (2, 3, 13, 14, 15)) and abs(speed) >= 512
        if not valid:
            flush(); segment = []; continue
        if segment and (row[0]-segment[-1][0] > .03 or any(row[i] != segment[-1][i] for i in (1, 8, 10))):
            flush(); segment = []
        segment.append(row)
    flush()
    return dict(axes={axis: dict(values, native_hz=values['ticks']/values['seconds'],
                                score_hz=values['score_frames']/values['audio_seconds'] if values['audio_seconds'] else None,
                                presentation_hz=values['display_intervals']/values['display_seconds'] if values['display_seconds'] else None)
                      for axis, values in totals.items()},
                scope='Physical radar-latch samples in active runs of at least 0.5 s with stable native '
                      'orientation/velocity and round; includes stationary frames within each run. '
                      'Native tick and elapsed score-frame counts, not a claim of equal distance through different maze paths.')
