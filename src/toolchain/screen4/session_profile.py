"""Profile the shared full session after keyboard advances to native round5.

Reuse the established matched PC/SP profiler and its uninstrumented control.
The fixture uses the production F5 input, never a replacement enemy routine.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path
import sys

if '--bundle' not in sys.argv:
    sys.argv.extend(('--bundle',str(Path.cwd()/'references/build/game')))
from session_reference import configure
configure(Path(sys.argv[sys.argv.index('--bundle')+1]))
adapter=source_path('game_profile.py').read_text()
at=adapter.index('exec(compile(source')
adapter=adapter[:at]+"from session_profile_adapter import adapt\nsource=adapt(source,base)\n"+adapter[at:]
exec(compile(adapter,str(source_path('game_profile.py')),'exec'),
     {'__file__':str(source_path('game_profile.py')),'__name__':'__main__'})
