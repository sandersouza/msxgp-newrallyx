"""Profile first-stage native/host logic without changing the measured ROM.

Uses the ordinary keyboard route and the PC/SP profiler, with finer callable
boundaries. Native addresses are already established call sites of game-core.inc.
The measured/control runs must retain identical guest state and timing.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path
import json


ROUTINES = {
    'Game_Prepare': 'Complete gameplay preparation',
    'Game_Frame': 'Elapsed native ticks',
    'Game_ReadInput': 'Read keyboard matrix and write original input latch',
    'Native_Input': 'Original RNG step at 8F24',
    'Native_Steering': 'Original round/fuel clock dispatcher at 83FD',
    'Game_LogicTick': 'Native/host gameplay tick',
    'Fuel_Tick': 'Fuel clock and pending bonus',
    'Native_FuelSpeed': 'Original periodic speed dispatcher at 8472',
    'Smoke_PreTick': 'Prepare ring retirement for native motion',
    'Full_MSXPlayerSpeed': 'Cap native player velocity',
    'Full_MSXBoundVelocity': 'Signed velocity cap helper',
    'Native_MotionDispatcher': 'Original 8069 player/enemy motion and animation',
    'Full_NativeMotion': 'MSX-native even-tick movement adapter',
    'Smoke_Tick': 'Original smoke worker and host notification',
    'Smoke_AfterNative': 'Smoke placement bookkeeping',
    'Native_PlayerFinalize': 'Original 9052 player steering and wall probes',
    'Full_MSXPan': 'MSX camera pan adapter',
    'Game_Animation': 'Four-tick animation clock',
    'Full_MSXAnimation': 'Native animation adapter',
    'Enemy_AfterMove': 'Contact, AI and native camera update',
    'Enemy_CameraOnly': 'Native camera-only update',
    'Full_MSXContact': 'World-space enemy contact scan',
    'Full_MSXAI': 'Even-tick enemy decisions',
    'Full_MSXActor': 'One enemy AI decision',
    'Full_MSXSmoke': 'Enemy smoke lookup',
    'Rock_Update': 'Rock contact scan',
    'Native_ContactCell': 'Original 9774 contact-cell geometry',
    'Flag_Update': 'Flag address scan',
    'Score_Update': 'Score event processing',
    'Fuel_Begin': 'Fuel reward dispatch',
    'Parameters_Update': 'Original speed/round parameter dispatch',
    'GameMulti_Parameters': 'Fixture population preservation',
    'Death_Begin': 'Contact to death transition',
    'Death_Tick': 'Death pause clock',
    'Round_Frame': 'Round completion transition',
    'Round_Tick': 'Round bonus worker',
    'Game_Events': 'Gameplay to audio/terrain events',
    'Game_Position': 'Native descriptor to world position',
    'Player_Axis': 'Native cell/fine coordinate conversion',
    'Player_AxisY': 'Native inverted Y conversion',
    'Game_Actors': 'Native descriptors to actor list',
    'GameSprites_Prepare': 'Actor sprite preparation',
    'GameHUD_Prepare': 'HUD preparation',
    'GameAudio_Tick': 'PSG worker',
    'render': 'Complete background preparation',
    'wait_blank': 'Synchronization waits including HALT',
    'commit': 'Complete presentation publication',
    'clock_irq': 'VBlank ISR body',
}

ALIASES = {
    'Native_Input': 0x8f24,
    'Native_Steering': 0x83fd,
    'Native_FuelSpeed': 0x8472,
    'Native_MotionDispatcher': 0x8069,
    'Native_PlayerFinalize': 0x9052,
    'Native_ContactCell': 0x9774,
}

driver = source_path('game_profile.py').read_text()
start = driver.index("source=source[:start]+'''ROUTINES = {")
end = driver.index("}'''+source[end:]", start) + len("}'''+source[end:]")
driver = driver[:start] + 'source=source[:start]+' + repr(
    'ROUTINES = ' + repr(ROUTINES)) + '+source[end:]' + driver[end:]

# Finer boundaries may legitimately be absent in the natural route. The shared
# driver owns both-endpoint action classification and the active-only ledger.
adapt = r'''
source=source.replace("    syms['HUD_NameStores'] = 0xa300", "    syms['HUD_NameStores'] = 0xa300\n    syms.update("+repr(ALIASES)+")")
source=source.replace("        assert rows, f'Unexercised routine: {name}'", "        if not rows:\n            stats.append(dict(name=name,purpose=purpose+' (not called)',calls=0,calls_per_frame=0,min=None,mean=None,p95=None,max=None,self_mean=None,self_total=0))\n            continue")
'''
marker = "exec(compile(source,"
driver = driver.replace(marker, adapt + '\n' + marker)
exec(compile(driver, str(source_path('game_profile.py')), 'exec'),
     {'__file__': str(source_path('game_profile.py')),
      '__name__': '__main__', 'ALIASES': ALIASES, 'json': json})
