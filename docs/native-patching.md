# Native patch and allocation contracts

These pure contracts implement #17, the first stage of #11. They do not boot
the original program or establish combined logic/render feasibility.

## Transactional program patches

`src/toolchain/msx/native_patch.py` exposes frozen `Patch` records and
`apply_patches(image, expected_sha256, patches, boundaries)`. Supply a complete
16 KB image reconstructed from contributor ROMs after the pinned inventory has
been validated. The expected full-program digest must come from the reviewed
supported revision, not be learned from an untrusted build input.

Each patch supplies an original address, expected original-span SHA-256,
immutable replacement bytes and an original continuation address. Replacement
length determines the guarded span. Both span endpoints and the continuation
must be evidenced instruction boundaries. Pass a tuple of patches and a
frozenset of boundaries. The complete set is checked against the original image
before any result bytes are changed. Overlapping/duplicate spans, hash
mismatches, invalid ranges and operand boundaries fail with `ValueError`.
Input bytes/bytearrays are never modified; the result is immutable bytes.

This validator cannot prove the supplied instruction map or replacement code
is correct. Review executed traces, displaced instructions, registers/flags,
stack/interrupt semantics and stub ownership separately. Do not substitute a
linear disassembly for execution evidence or call `$0c2c` as a returning tick.
The current hook inventory is a candidate map, not a native patch recipe.

## CPU and asset allocations

`src/toolchain/msx/native_layout.py` exposes frozen half-open `Region(name, start,
end)` records, `validate_layout(regions)` and `pack_assets(resources,
capacity=65536)`.

Include every existing reservation and every proposed allocation in the same
exclusive inventory. Nonempty names are unique; ranges stay within the 64 KB
CPU address space and a single 16 KB page. Adjacent allocations are legal;
overlap or spilling a resident image into the next page is rejected. Validate
owner ranges and their contained allocations as separate inventories.
The caller must also prove placement in the correct owner page and select
eight distinct physical mapper segments; disjoint CPU ranges do not establish
physical mapper isolation.

Asset packing sorts resource names deterministically, returns offset/length
pairs and zero-pads whole 16 KB segments. The default is four segments (65,536
bytes); smaller whole-segment capacities are accepted. Overflow is rejected
without truncating or modifying inputs. Resource offsets can span segments;
the eventual reader must switch segments at each physical boundary.

No active native asset working set or final linked stub layout is claimed by
these helpers. Loader/resource fit and actual mapper isolation remain #19 gates.

## Verification

Run synthetic checks without original game data:

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_native_*.py' -v
make test
```

The initial local contributor-input exercise checked all 11 original hook spans
and 11 reserved CPU regions using reviewed #10 trace endpoints. It used identity
replacements only and confirmed source hashes remained unchanged. Its local
sealed report is under `references/analysis/issue-11-contracts-c53c8fabe66b4c6e8d333a319ae45b92/`.
That report contains no applied native adapters and is not gameplay evidence.
Original bytes, trace instruction text, generated cartridges and captures remain
ignored; synthetic tests contain authored instructions only.
