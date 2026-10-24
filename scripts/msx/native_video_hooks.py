"""Guarded first-stage scenery invalidation; original instructions stay local."""
from .native_patch import Patch

HOOKS = (
    (0x0651, 4, 'ix:0', '7323285b69f7aed500265bf501f7ac2c452f00b70e76bfeea822cb0da9a1f4a9'),
    (0x0655, 4, 'ix:31', 'cb844c04074c54dfa6044d650dc4be1e58c05e339e713aaa3f360be0751c51be'),
    (0x0659, 4, 'ix:32', '882c642aca5aaace1b628955ffbcd1f17cba590b7a00cc0462e0598f36d65496'),
    (0x0663, 4, 'ix:63', '845c78f383dc87fbf0da3249e56d43b45927b9dc9ace3be272031718d8060068'),
    (0x0667, 4, 'ix:64', 'ddeecfd543765ee24d07ba60fa329cb9c6799e58045ef6b786b5343069b1652d'),
    (0x066b, 4, 'ix:95', 'b307b92d5d586986e1090ea730aa56a5e18dbaa3d5aa096ac5365295a5f9e814'),
    (0x066f, 4, 'ix:96', '2f1cc33a4fd10fa20de218d9591448d18c89dea05c2854253ad9d03707352491'),
    (0x067d, 4, 'ix:0', '0fbd186f0897157bbdba6dbb7723be277b5ad6cfadbdeaaacadc81fd91664631'),
    (0x0681, 4, 'ix:1', '399597072b3fc08878d5a4ac3d3fd94d51549c81da929be338803d698b6cdcbb'),
    (0x0685, 4, 'ix:32', '5d82dfd883b1b669d8b4a9b647dce8490bb00bcec885aeae2a199bc5d567c46e'),
    (0x0689, 4, 'ix:33', '43ed9d24e55d2fbbf6aa74089b9dfdf7c9911ccbd0d6d1c6fda89c835aec741b'),
    (0x0722, 5, 'de', 'df1344000189fc644b0163ce207b0f30fabcde91af059f6a4f4dfe6382ef7fb4'),
    (0x0733, 3, 'hl', 'c83af65812540689af0301128ad143f45a4b44fc9c7672fddcc40adc0f20bf28'),
    (0x0ff1, 4, 'both', 'b4048ee019b0987150dfdb400b91515dc4e1e773219ca257599d33c3f3e6200b'),
    (0x0fe7, 4, 'hl', 'e957e6f2979ef1e0dfa76c2c13347f8315570727213fd19bd7e1eabe7cb5a504'),
    (0x1568, 3, 'changed:hl:c:0', '473c08e6b8c635ce1ef0e4f4adafa002effd6aa1c85edf327aed6d573dc50518'),
    (0x156b, 5, 'changed:hl:a:4', '21f393fa28830aef1a5f83aa9d9e2ea0acfd403d4c1a487f1f973c8520c02007'),
    (0x1598, 3, 'changed:de:a:2', '647bc4020bad0d5981598e106dcb386a8f97ca8d916194187ce69fac1a562b3c'),
    (0x159b, 4, 'changed:hl:b:3', 'fc1d16f0a9552410915588c0c6ba64197829567005d63603dbf8e5ebe13300e4'),
    (0x15ae, 3, 'changed:de:a:0', '1341a93b3db11ca4fb884856da11674395aae355306cc6a40bb45f7162abcb1e'),
    (0x1984, 3, 'both', '295eb0fa64f8167e05734565ba5217a15ee0229c1b199e24e69c7167e38f4c2f'),
    (0x1d2a, 3, 'block', 'fa4baf88577be2e274235ed84cb8b773f29f9909dd3d74994bece1c046005a33'),
    (0x1e41, 3, 'range', 'ea71ae24e1548fefc87ec2ce53885b163f2c5ab594042714070c10651a1673b2'),
    (0x20e5, 3, 'all', '0beb14ea832c315efa1ced41a58674bd9f22c1894576eab9e940d4dc73e4f93d'),
    (0x2158, 3, 'hl-left', '03cd537e269f5a3b7864e7cd84c8010ee212801ebb30ffa11ee761765c507c5b'),
)


def patches(symbols):
    result = []
    for address, length, _, sha in HOOKS:
        target = symbols.get(f'Native_VideoAdapter_{address:04x}')
        if type(target) is not int or not 0x4000 <= target < 0x8000:
            raise ValueError('Video adapter must be resident')
        result.append(Patch(address, sha, bytes((0xc3, target & 255, target >> 8)) +
                            bytes(length-3), address+length))
    return result


def trampolines():
    lines = []
    for address, length, kind, _ in HOOKS:
        lines.append(f'Native_VideoAdapter_{address:04x}:')
        if kind.startswith('changed:'):
            _, base, value, prefix = kind.split(':')
            prefix = int(prefix)
            if prefix:
                lines.append(f'    INCBIN "native-source.bin",${address:04x},{prefix}')
            lines.append('    push af')
            if base == 'de':
                lines.append('    ex de,hl')
            if value != 'a':
                lines.append(f'    ld a,{value}')
            lines.extend(['    cp (hl)', '    call nz,Native_MarkTileHL'])
            if base == 'de':
                lines.append('    ex de,hl')
            lines.extend(['    pop af',
                          f'    INCBIN "native-source.bin",${address+prefix:04x},{length-prefix}',
                          f'    jp ${address+length:04x}'])
            continue
        if kind.startswith('ix:'):
            offset = int(kind.split(':')[1])
            lines.extend(['    push af', '    push bc', '    push hl',
                          '    push ix', '    pop hl', f'    ld bc,{offset}',
                          '    add hl,bc', '    call Native_MarkTileHL',
                          '    pop hl', '    pop bc', '    pop af'])
        if kind in ('hl', 'both', 'hl-left'):
            lines.append('    call Native_MarkTileHL')
        if kind == 'hl-left':
            lines.extend(['    dec hl', '    call Native_MarkTileHL', '    inc hl'])
        if kind in ('de', 'both'):
            lines.append('    call Native_MarkTileDE')
        if kind == 'all':
            lines.append('    call Native_RequestAllTiles')
        if kind == 'range':
            lines.append('    call Native_MarkTileRange')
        if kind == 'block':
            lines.extend(['    push bc', '    push hl', '    inc hl',
                          '    ld c,(hl)', '    ld b,0',
                          '    call Native_MarkTileRange', '    pop hl', '    pop bc'])
        lines.extend([f'    INCBIN "native-source.bin",${address:04x},{length}',
                      f'    jp ${address+length:04x}'])
    return '\n'.join(lines) + '\n'
