# Original graphics extraction design

Issue: [#1](https://github.com/sandersouza/msxgp-newrallyx/issues/1).
Design direction approved in this chat on 2026-10-20. This document specifies
the implementation for review; it does not record completed extraction work.

## Goal and boundaries

Provide a reproducible local Python extractor for contributor-supplied New
Rally-X ROMs. Preserve graphic identifiers, dimensions, pixel indices and palette
choices so later port work can inspect the original representation.

Support one unpacked `nrallyx` set. Exclude ZIP handling, downloading ROMs,
disassembly, map reconstruction, sound extraction, gameplay, scene rendering and
MSX conversion. ROMs, derived assets and reference captures remain in ignored
`references/` directories. Only code, synthetic tests, documentation and metadata
may be committed. Commits and pushes require separate user authorization.

## Verified starting point

- The local main branch already includes the macOS bootstrap from issue #2.
- Existing `.venv` provides Python 3.14.7 and Pillow 13.0.0. Reuse the project's
  Python 3.14 contract and `requirements.txt` pin; add no runtime dependency.
- Installed MAME reports 0.289.
- All 13 files under `references/roms/nrallyx/` match the sizes, CRC32 and SHA-1
  reported by that MAME executable's `-listxml nrallyx` output.
- No decoder or visual comparison has been performed yet.

## Provenance and supported inputs

Pin MAME tag `mame0289`, peeled commit
`f34f02505e32c1993c6a782b6814232cbfc74e36`. Upstream references:

- [src/mame/namco/rallyx.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx.cpp):
  `ROM_START(nrallyx)`, graphics layouts and decode entries.
- [src/mame/namco/rallyx_v.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/mame/namco/rallyx_v.cpp):
  palette conversion, lookup selection, flips and transparency behavior.
- [src/emu/video/resnet.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/emu/video/resnet.cpp)
  and its header: resistor network calculation and rounding.
- [src/emu/drawgfx.cpp](https://github.com/mamedev/mame/blob/f34f02505e32c1993c6a782b6814232cbfc74e36/src/emu/drawgfx.cpp):
  bit addressing and plane significance for graphic decoding.

Commit `scripts/graphics/nrallyx.json` containing the source revision, ROM set
name, all 13 filenames, physical file sizes, CRC32, SHA-1, region roles and graphics
load offsets. Verify metadata against the pinned source as well as installed
MAME XML before accepting it. CPU ROM sizes include `ROM_CONTINUE` segments.

Validate the entire supported set, including files not decoded by this tool.
Missing files, wrong sizes and checksum mismatches must name the affected file
and expected values. Report these as an incomplete, corrupt or unsupported set;
do not guess another revision or rename files. Reject symbolic links and
nonregular required files. Unrelated extra files do not invalidate a matching
set. Open required inputs read-only and retain the validated bytes for decoding
so input changes cannot silently alter the extracted data after validation.

## CLI and components

Document this invocation from the repository root:

```sh
.venv/bin/python scripts/extract_graphics.py \
  --input references/roms/nrallyx \
  --output references/assets/nrallyx
```

Both paths are required. Relative paths are relative to the caller's working
directory; the permitted output root is anchored to the script's repository.
`--help` documents the supported set, path restrictions and `--overwrite`.
Exit zero only when a complete output directory is published. Validation and
I/O errors produce concise actionable stderr messages and nonzero status.

- `scripts/extract_graphics.py`: argument parsing and error reporting.
- `scripts/graphics/roms.py`: metadata loading and input validation.
- `scripts/graphics/decode.py`: pure indexed graphics and palette decoding.
- `scripts/graphics/export.py`: output safety, atlases, manifests and publication.
- `tests/test_extract_graphics.py` and focused helper files as necessary:
  entirely synthetic decoder, validation and export checks.
- `docs/graphics-extraction.md`: usage, schema, provenance and validation results;
  link it from README.

This separation keeps filesystem policy outside the pure decoder and allows
tests without proprietary inputs or a running emulator.

## Graphics and color contract

Decode the shared graphics region in its original order into 256 characters
(8 by 8 pixels) and 64 sprites (16 by 16 pixels). Decode eight radar/dot shapes
(4 by 4 pixels) from their separate PROM. Retain all IDs, including empty or
duplicate graphics. Implement the pinned layouts' bit offsets and plane
significance explicitly; do not infer orientation from appearance.

Canonical pixels use the unflipped source orientation and values 0 through 3.
Document runtime flip interpretation separately; synthetic asymmetric patterns
must verify horizontal, vertical and combined reflection without reassigning IDs.

Expose all 32 indirect RGB palette entries and the 256-entry lookup PROM,
including raw bytes and effective indices. Match MAME's resistor network and
rounding. Enumerate all 64 character/sprite color codes, even unused or identical
variants; dots use their dedicated palette mapping.

Export tile atlases as opaque graphics. Sprite transparency depends on whether
the selected lookup entry maps to indirect color zero, rather than on RGB black
or a fixed source pen. Dots use source pen 3 as transparent for isolated previews.
Store transparency rules alongside color mapping so black and transparency remain
distinguishable. Isolated PNGs do not reproduce scene priority or bullet/sprite
palette-bank interaction; document that limitation explicitly.

## Output schema, version 1

Within the selected output directory:

| Path | Content |
| --- | --- |
| `tiles/indices.bin` | 256 consecutive 8x8 graphics; one unsigned byte per pixel |
| `sprites/indices.bin` | 64 consecutive 16x16 graphics; one unsigned byte per pixel |
| `dots/indices.bin` | Eight consecutive 4x4 graphics; one unsigned byte per pixel |
| `tiles/atlas-indexed.png` | P-mode atlas with source pen indices 0..3 and a neutral inspection palette |
| `sprites/atlas-indexed.png` | Same source-index convention for sprites |
| `dots/atlas-indexed.png` | Same source-index convention for dots |
| `tiles/color-00.png` through `color-63.png` | Opaque original lookup variants |
| `sprites/color-00.png` through `color-63.png` | Original lookup variants with alpha transparency |
| `dots/color-00.png` | Dedicated dot colors and isolated-preview transparency |
| `palette.json` | Raw PROM bytes, RGB colors, lookup entries and transparency rules |
| `graphics.json` | Counts, dimensions, index encoding, source layout, flips and atlas positions |
| `manifest.json` | Provenance, tool/schema versions, dependencies, parameters, input and output hashes |

Binary ordering is graphic ID, row, column; origin is top left. Atlas slots run
left to right, then top to bottom, with 16 columns for tiles, eight for sprites
and eight for dots. No scaling, labels, padding or deduplication. Thus tile and
sprite atlases are 128x128; dot atlases are 32x4. JSON describes ID-to-slot mapping.
Color variants may be RGBA; the binary and indexed atlas preserve source indices.

Sort JSON keys, input records and output records; use UTF-8 with a trailing newline.
Use fixed PNG options and omit incidental image metadata. Output SHA-256 records
cover every payload file except `manifest.json` itself, avoiding a circular hash.
Record input size, CRC32 and SHA-1; record tool version, schema version, Pillow
version, Python version and extraction parameters. Exclude timestamps, absolute
paths and host-specific environment details. Byte-for-byte reproducibility is
required for identical inputs, tool and recorded runtime versions; cross-version
PNG encoding reproducibility is not promised.

## Output safety and failures

Accept only a strict descendant of this repository's `references/assets/`.
Reject the assets root itself, any path containing `..`, symlink components,
non-directory ancestors and any overlap with the input directory. Verify that
generated paths are ignored by Git and that no existing destination file is
tracked. Reject unsafe paths even with `--overwrite`.

If the destination exists, refuse by default. `--overwrite` may replace only a
directory recognized as this tool's complete version-1 output: its manifest,
file inventory and hashes must match, with no unknown files or symbolic links.
Never erase an arbitrary directory or silently discard modified assets.

Validate inputs before creating output. Write to a unique ignored sibling
staging directory, compute checksums and write the manifest last. Publish a new
destination by renaming the complete staging directory. For overwrite, move the
old validated directory to a sibling backup, install the staged result, then
remove the backup. Roll back on ordinary publication errors. Clean up staging
on handled failure without changing inputs or an existing output. A process
crash during the overwrite rename window can leave a backup; report recovery
instructions and never treat staging/backup directories as completed extraction.
Concurrent extraction to the same destination is unsupported and must be refused
with a destination-specific exclusive lock. The tool does not run as a security
boundary against another process modifying filesystem paths concurrently.

## Verification and delivery

Use the existing unittest workflow and Python/Pillow environment. Write failing
synthetic tests before decoder and validation implementation. Tests cover known
bit positions, plane weights, graphic boundaries, asymmetric flips, RGB resistor
weights/rounding, all lookup variants, lookup-based sprite transparency, dot
transparency, binary ordering and atlas positions. Synthetic all-zero and
single-bit PROMs must be generated in tests rather than copied from ROMs.

Filesystem/CLI tests cover missing, wrong-size and same-size corrupt inputs,
unsupported sets, unsafe paths, symlinks, destination collisions, overwrite
preservation, publication failures and deterministic outputs. Exercise checksum
validation using temporary synthetic ROM files and matching test metadata; the
production CLI must not expose a checksum bypass or arbitrary metadata override.

Local integration uses contributor ROMs only: hash inputs before and after,
extract twice into separate ignored destinations and compare all output hashes.
Inspect raw and colored graphics against the MAME 0.289 graphics viewer for
each graphics bank, multiple IDs and color codes, including first/last entries,
asymmetric shapes, sprites, dots and transparency-sensitive colors. Record the
exact IDs, color codes, commands, observed agreement and discrepancies in the
development document. Keep captures under ignored `references/`; if the viewer
cannot be inspected, report that criterion as pending rather than claiming it.

Run the full existing test suite, extraction help, local integration and
`git check-ignore` for ROMs, outputs, staging and captures. Inspect Git's tracked
files and the final diff for original data. Documentation must include direct
minimal installation with Python 3.14, a local venv and `requirements.txt` as well
as the existing bootstrap command.

Implement on `feat/1-extract-assets`; move the project item to In progress when
implementation starts and to In review while delivery/review remains pending.
Keep the local issue draft aligned with published progress. Do not close issue #1
until its acceptance criteria and delivery conditions are met; commit, push and
PR delivery remain subject to repository authorization.
