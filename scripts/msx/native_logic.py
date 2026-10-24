"""Pinned original-address adapters; displaced original bytes stay local."""
import hashlib
import json
from pathlib import Path

from .native_patch import Patch, apply_patches
from .native_reset import PROGRAM_SHA256, reset_patches


def profile():
    return json.loads(Path(__file__).with_name('native_logic_hooks.json').read_text())


def coordinate_deltas() -> bytes:
    """Authored arithmetic, independent of original program bytes or snapshots."""
    return bytes(((-2 if (a+35)&128 else ((a+35)&255)//24-1)&255)
                 for a in range(256))


def patch_logic(image: bytes, symbols: dict, boundaries: frozenset[int], *, optimize=False, video=False) -> bytes:
    if type(optimize) is not bool or type(video) is not bool:
        raise ValueError('Optimization selection must be a boolean')
    if hashlib.sha256(image).hexdigest() != PROGRAM_SHA256:
        raise ValueError('Unsupported complete logic program')
    patches = list(reset_patches(symbols['Native_ResetFinalize']))
    if video:
        from .native_video_hooks import patches as video_patches
        patches.extend(video_patches(symbols))
    for hook in profile()['hooks']:
        if hook.get('optional') == 'coordinate-loop' and not optimize:
            continue
        n,kind = hook['length'],hook['kind']
        if kind == 'nop':
            replacement = bytes(n)
        elif kind == 'coordinate-table':
            table = symbols.get('Native_CoordinateDelta')
            if type(table) is not int or not 0x4000 <= table <= 0x7f00 or table & 255:
                raise ValueError('Coordinate delta table must be resident and page-aligned')
            # Authored PUSH DE; LD E,A; LD D,table-page; LD A,(DE);
            # ADD A,L; LD L,A; POP DE; AND A; RET. Full flags come from AND.
            replacement = bytes((0xd5,0x5f,0x16,table>>8,0x1a,0x85,
                                 0x6f,0xd1,0xa7,0xc9))+bytes(n-10)
        elif kind == 'input':
            address = hook['input']
            replacement = bytes((0x3a,address & 255,address >> 8))
        else:
            name = hook.get('target',f'Native_Adapter_{hook["address"]:04x}')
            target = symbols.get(name)
            if type(target) is not int or not 0x4000 <= target < 0x8000:
                raise ValueError('Native adapter target must be resident page-1 code')
            replacement = bytes((0xc3,target & 255,target >> 8))+bytes(n-3)
        patches.append(Patch(hook['address'],hook['sha256'],replacement,hook['continuation']))
    return apply_patches(image,PROGRAM_SHA256,tuple(patches),boundaries)


def trampoline_source() -> str:
    """Emit authored control flow; INCBIN slices refer only to ignored sources."""
    lines,eligible = [],[]
    def original(spans):
        for address,length in spans:
            lines.append(f'    INCBIN "native-source.bin",${address:04x},{length}')
    def virtual(enabled):
        lines.extend(['    push af',f'    ld a,{int(enabled)}',
                      '    ld (Native_VirtualIFF),a','    pop af'])
    for hook in profile()['hooks']:
        kind,address = hook['kind'],hook['address']
        if kind in ('nop','input','jump','coordinate-table'):
            continue
        lines.append(f'Native_Adapter_{address:04x}:')
        if kind == 'poll':
            lines.append('    call Native_ReadyPoll')
        if kind == 'poll-branch-zero':
            lines.extend(['    jp nz,.ready','    call Native_ReadyPoll',
                          f'    jp ${hook["loop"]:04x}', '.ready:'])
        if kind in ('wait-three','wait-count'):
            lines.extend(['    call Native_WaitTick']*(3 if kind == 'wait-three' else 1))
            if kind == 'wait-count':
                lines.extend(['    dec a',f'    jp nz,${address:04x}'])
            lines.append(f'    jp ${hook["continuation"]:04x}')
            continue
        original(hook.get('pre',[]))
        if kind == 'loop-ei-return':
            lines.append('    djnz .again')
            virtual(True)
            lines.extend(['    ei','    ret','.again:',f'    jp ${hook["loop"]:04x}'])
            continue
        if kind == 'transfer-ei':
            lines.extend(['    call Native_CompleteTransfer',
                '    push af','    ld a,(Native_TransferPublish)','    or a',
                '    jr z,.no_event','    xor a','    ld (Native_TransferPublish),a',
                '    pop af','    ld (Native_Published),a','    jr .after_event',
                '.no_event:','    pop af','.after_event:'])
        if kind == 'read-bc-di':
            lines.extend(['    call Native_ReadBC','    ld b,a'])
        if kind in ('ei','transfer-ei','di','read-bc-di'):
            virtual(kind in ('ei','transfer-ei'))
        if kind in ('ei','transfer-ei'):
            lines.append('    ei')
        if kind == 'read-hl':
            lines.append('    call Native_ReadHL')
        if kind == 'increment-read':
            lines.append('    call Native_IncrementRead')
        if kind == 'write-de':
            lines.append('    call Native_WriteDE')
        original(hook.get('post',[]))
        if kind in ('ei','transfer-ei'):
            # Accept an already pending interrupt only after the original EI
            # delay instruction. The jump-only continuation has no data effect;
            # use an equivalent deferred jump before servicing its target.
            if not hook.get('post'):
                lines.extend(['    jp .deferred','.deferred:'])
            lines.append('    call Native_Poll')
        tail = f'Native_Eligible_{address:04x}'
        lines.append(tail+':')
        eligible.append(tail)
        lines.append(f'    jp ${hook["continuation"]:04x}')
    lines.append('Native_EligibleIRQPCs:')
    lines.extend(['    dw Native_WaitTick.afterDispatch','    dw Native_WaitTick.afterHalt'])
    lines.append('    dw Native_Poll.resume')
    lines.extend('    dw '+label for label in eligible)
    lines.append('    dw 0')
    return '\n'.join(lines)+'\n'
