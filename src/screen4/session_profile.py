"""Profile the shared full session after keyboard advances to native round5.

Reuse the established matched PC/SP profiler and its uninstrumented control.
The fixture uses the production F5 input, never a replacement enemy routine.
"""
from pathlib import Path
import sys

if '--bundle' not in sys.argv:
    sys.argv.extend(('--bundle',str(Path.cwd()/'references/experiments/full-session')))
adapter=Path(__file__).with_name('game_profile.py').read_text()
at=adapter.index('exec(compile(source')
adapter=adapter[:at]+"from session_profile_adapter import adapt\nsource=adapt(source,base)\n"+adapter[at:]
exec(compile(adapter,str(Path(__file__).with_name('game_profile.py')),'exec'),
     {'__file__':str(Path(__file__).with_name('game_profile.py')),'__name__':'__main__'})
