"""Reproduce the exact pre-nine-cycle512KiB package in an ignored test owner.

Reverse the later cold-lifecycle fixes and common phase-exit register reuse.
This is a historical reproduction, including the diagnosed special-flag and
challenge-resume defects; never use it as a current quality acceptance target.
Do not replace the candidate/default artifacts or expose a production switch.
"""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mapper512_game as game
from mapper512_integrate import build
from compact_game_build import replace


def baseline(keep_phase_target=False):
    original=(game.adapt,game.RUNTIME,game.OUT,game.object_templates)
    def adapt(assembly,rom,raw_pages):
        plan=original[0](assembly,rom,raw_pages)
        if not keep_phase_target:
            p=assembly/'session-phase.inc';text=replace(p.read_text(),'    ld a,b\n    or $c0','    ld a,(phase)\n    or $c0')
            text=replace(text,'\n    defs 2,0 ; Retain downstream API addresses after the shorter load.\n','')
            p.write_text(text)
        p=assembly/'modules/session/world.inc'
        p.write_text(replace(p.read_text(),'    dw $bd80,$bda4,$bdc8,$bdec','    dw $bd80,$bd9b,$bdb6,$bdd1'))
        p=assembly/'modules/session/lifecycle.inc'
        p.write_text(replace(p.read_text(),'    call Mapper512_ResumeVideo','    call GameSession_Video'))
        p=assembly/'lab.asm';text=p.read_text();start=text.index('; Cold challenge resume only;')
        end=text.index('    ASSERT $ < $8000',start);p.write_text(text[:start]+text[end:])
        plan['phase_target_reuse']=keep_phase_target
        return plan
    try:
        game.adapt=adapt
        game.object_templates=lambda themes:b''.join(raw[0x2800:0x281b] for raw in themes)
        owner='game-mapper512-lifecycle-control' if keep_phase_target else 'game-mapper512-sync-baseline'
        game.RUNTIME=game.ROOT/'references/build'/f'{owner}-runtime'
        game.OUT=game.ROOT/'references/build'/owner
        build(game.RUNTIME,game=True);plan=game.package()
        expected=(json.loads((game.ROOT/'docs/measurements/timing/mapper512-audio-sync.json').read_text())['candidate'] if keep_phase_target
                  else json.loads((game.ROOT/'docs/measurements/cartridge/issue42-512-native-game.json').read_text())['plan'])
        assert plan['resource_sha256']==expected['resource_sha256'] and plan['bridge_sha256']==expected['bridge_sha256']
        assert plan['active_images']==expected['active_images'] and plan['files']==expected['files']
        return plan
    finally:game.adapt,game.RUNTIME,game.OUT,game.object_templates=original


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--keep-phase-target',action='store_true');p=a.parse_args();baseline(p.keep_phase_target)
