"""Stable delivery names and compatibility readers for historical measurements."""
from pathlib import Path


def cartridge_path(bundle):
    bundle = Path(bundle)
    current = bundle / 'newrallyx.rom'
    historical = bundle / 'fixed-hud.rom'
    return current if current.exists() or not historical.exists() else historical


def variant_parts(build, hud='compact'):
    parts = []
    if build['banks'].get('SESSION_TEST_MODE', 0):
        parts.append('test')
    diagnostics = []
    if hud == 'classic':
        diagnostics.append('classic-hud')
    if not build['banks'].get('SESSION_MSX_LOGO', 1):
        diagnostics.append('no-logo')
    if not build['banks'].get('SESSION_HARDWARE_CHECK', 1):
        diagnostics.append('no-check')
    if not build.get('turbo', False):
        diagnostics.append('base-cpu')
    if not build.get('ram_auto', False):
        diagnostics.append('ram' + str(build.get('ram_kib', 128)))
    if diagnostics:
        parts += ['diagnostic', '-'.join(diagnostics)]
    return parts


def delivery_directory(root, build, hud='compact'):
    return Path(root).joinpath('dist', *variant_parts(build, hud))
