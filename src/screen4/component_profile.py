"""Read-only component profiler: reuse the matched-PC/SP route/control driver.

Adds callable music, effects, PSG, terrain and HUD boundaries. Raw evidence and
an immutable ROM copy stay under the ignored experiment bundle. No guest code
or native population is modified by this probe.
"""
from pathlib import Path
import json

EXTRA = {
    'GameAudio_MusicTick': 'Music sequence advancement (30 Hz)',
    'GameAudio_NoiseTick': 'Engine and queued sound effects (30 Hz)',
    'GameAudio_RenderMusic': 'Music/effects mix and changed PSG output',
    'GameAudio_WritePSG': 'Changed PSG register writes',
    'GameHUD_Commit': 'Dynamic HUD sprite publication',
    'GameSprites_Commit': 'World sprite publication',
    'Ring_Prepare': 'Incoming world ring cells',
    'Ring_LoadColumns': 'Incoming world columns',
    'Ring_LoadRun': 'World ID lookup run',
    'Ring_UploadNames': 'Terrain name table publication',
    'Ring_UploadColumn': 'Column VRAM upload',
    'Ring_UploadRow': 'Row VRAM upload',
    'Game_RingPatch': 'Flag/smoke/death terrain overrides',
    'GameSmoke_BuildCache': 'Ordered smoke records with one retained-Y decode per row',
    'Game_PatchSquare': 'Clipped3x3 flag/death overlay',
    'Game_PatchOne': 'One cached terrain override and dirty mark',
    'Game_RestoreOne': 'Original map lookup for one retired effect cell',
    'GameDirty_Mark': 'Queue a changed name for both inactive tables',
    'Game_DirtyTileUpload': 'Changed terrain tile publication',
    'Game_Radar': 'Radar pattern preparation',
    'Game_RadarUpload': 'Radar VRAM transfers',
    'GamePhase_Select': 'Select an inactive exact cached phase or bounded victim',
    'hud_upload': 'Static HUD fine-scroll phase packet',
    'HUD_NameStores': 'Compiled fixed-HUD name stores',
    'left_names': 'Wrapped HUD guard name stores',
    'boundaries': 'HUD boundary name selection',
    'GameBoundary_Upload': 'Changed boundary pattern and color bytes',
    'GameDirty_Plan': 'Select sparse writes or complete name refill',
    'GameNameStream_Wide': 'Name strips for camera deltas of 2 or 3 tiles',
    'GS_MaskedCopyFast': 'Exact full-height horizontal sprite mask copy',
}
source = Path(__file__).with_name('game_logic_profile.py').read_text()
source = source.replace("driver = Path(__file__)",
                        "ROUTINES.update(EXTRA)\n\ndriver = Path(__file__)", 1)
exec(compile(source, str(Path(__file__).with_name('game_logic_profile.py')), 'exec'),
     {'__file__': str(Path(__file__).with_name('game_logic_profile.py')),
      '__name__': '__main__', 'EXTRA': EXTRA, 'json': json})
