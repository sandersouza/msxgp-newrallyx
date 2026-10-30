# Assembly modules and zero-cost integration contracts

These modules implement the user-authorized source-only subtask of
[issue 36](https://github.com/sandersouza/msxgp-newrallyx/issues/36), coordinated
with [issue 32](https://github.com/sandersouza/msxgp-newrallyx/issues/32).
The contract registry is [contracts.json](contracts.json); the frozen
pre-extraction binary/map fingerprints are [baselines.json](baselines.json).

## Integration model

Each registered entry also carries its input/output, register/IFF, memory and
reuse contract in source comments. Keep those summaries synchronized with
`contracts.json`. The [developer guide](../../../docs/developer-guide.md) and
[engineering lessons](../../../docs/engineering-lessons.md) explain the decisions
behind these boundaries; old generated experiments are not required reading.

Selection happens through assembly `INCLUDE`, just as with the
[HUD modules](../hud/README.md). An entry includes its existing implementation
at the existing code position. It does not add a call, jump, wrapper, loader,
runtime enable flag, function-pointer table, buffer or code/data copy. No
`MODULE` scope is introduced: existing global and local labels remain the ABI.

The full-session resident and cold files are now ordered compositions of
cohesive sources. The old `session-resident.inc` and `session-cold.inc` paths
remain compatible entry points. Resident helpers stay in fixed cartridge
4000..7FFF; cold code stays in the main Page0 segment at 1400..1FFF. Moving a
source file does not make it safe to move the linked code to another memory page.

The first-stage and complete-session presenters share the assembly facades;
their native/input/audio/cache bindings remain distinct. SCREEN 5 is independently
maintained and does not import these SCREEN 4 modules. Its baseline stays intact.

`lab.asm` remains the host's boot/frame/clock orchestration and VDP macro context;
the source-transform pipeline still selects its hardware profile. Native game
rules and resource generators are not converted into a runtime plugin system.
An arbitrary callback/event bus, dynamic allocator or universal scheduler would
change the execution contract and is intentionally excluded. Existing independently
includable mechanisms remain separate files; native bindings are explicitly
identified rather than advertised as general-purpose game logic.

## Public module map

| Entry | Responsibility and public API | Reuse boundary |
| --- | --- | --- |
| [vdp/transfers.inc](vdp/transfers.inc) | `GamePacketFast_Transfer`: bounded OUTI/OTIR stream. | Independent mechanism; caller owns source bank, data port and VDP address. |
| [vdp/registers.inc](vdp/registers.inc) | `register`, `stage_wait_command`. | Independent VDP mechanism with the host `reg` macro; command wait is cold-only. |
| [mapper/page0.inc](mapper/page0.inc) | Map/restore Page0, copy 16 KiB, patch a 3x3 world object. | Two host-defined segment aliases; fixed 128x256 map geometry. |
| [renderer/msx2.inc](renderer/msx2.inc) | Cache, world preparation, dirty names, smoke rows, radar, boundary and transfer composition. | Supply the matching world/event/actor adapters, layout and generated resources. |
| [native/core.inc](native/core.inc) | Native simulation, camera and actor binding. | Game-specific relocated seed, native entry points, host and multi-worker. |
| [actors/msx2.inc](actors/msx2.inc) | `GameSprites_Init`, `Prepare`, `Commit`, exact mask/clip workers. | Explicit six-byte actor/template/palette/VRAM ABI; complete drawings and real sprite limits. |
| [audio/first-stage.inc](audio/first-stage.inc) | Resident event/packet PSG worker. | Generated score/noise tables, private DC00 state; no native-state reads. |
| [session/runtime.inc](session/runtime.inc) | Full-session resident state/mapper/flags/bank-table composition. | Replaces the first-stage audio slot at assembly time; same original linked order. |
| [session/state.inc](session/state.inc), [session/boot.inc](session/boot.inc) | Native aliases and cold bootstrap/seed restoration. | Session policy, not a general RAM allocator or loader. |
| [session/world.inc](session/world.inc), [session/lifecycle.inc](session/lifecycle.inc) | Cold round/map loading; menu, death, challenge and turn transitions. | Existing native state/layout/callback semantics. |
| [renderer/session-banks.inc](renderer/session-banks.inc), [renderer/video.inc](renderer/video.inc) | Theme/phase mapping, cache prewarm and cold video restoration. | Packed eight-set SCREEN 4 layout; prewarm only while display is off. |
| [radar/cache-build.inc](radar/cache-build.inc), [radar/color.inc](radar/color.inc) | Cold glyph/name caches, physical-clock blink and color priority. | Native flag/actor encoding and accepted palette. |
| [audio/session.inc](audio/session.inc), [audio/stop-completion.inc](audio/stop-completion.inc) | Native request-driven PSG, silence and completion settlement. | Different Tick/event ABI from first-stage audio; never include both implementations. |
| [interface/decorations.inc](interface/decorations.inc), [interface/bitmap.inc](interface/bitmap.inc) | Player labels, point inscriptions and cold bitmap copy. | Existing UI/game scratch lifetimes and generated source banks. |
| [input/motion.inc](input/motion.inc), [session-input.inc](../session-input.inc) | Native corner rollback, round accessor, keyboard/joystick and input edge policy. | Native encodings and ordering; another game supplies an adapter instead of a runtime branch. |
| [session-pattern-address.inc](../session-pattern-address.inc), [session-phase.inc](../session-phase.inc) | Packed pattern-set address and inactive phase selection. | Existing virtual offsets, cache aliases and cost-table geometry. |
| [session-startup-options.inc](../session-startup-options.inc) | Optional cold replay/skip module. | Include plus generator selection controls code/resources; `HARDWARE_CHECK=0` emits no active polling. |
| [hud/compact.inc](../hud/compact.inc), [hud/classic.inc](../hud/classic.inc) | Complete selected HUD with native input adapter. | Existing HUD contract and original glyph/data encodings. |

The small [radar/blink.inc](radar/blink.inc),
[session/ui-palette.inc](session/ui-palette.inc) and
[native/smoke-objects.inc](native/smoke-objects.inc) retain their adjacent
resident positions. They are native bindings: blink restores Page0 after one
pattern-bit write, palette includes the existing generated 32-byte resource,
and object/smoke hooks retain original state/entry assumptions. The cold
[vdp/cold-ui.inc](vdp/cold-ui.inc) composes register and bitmap helpers without
adding code. Do not include these again if the owning composition already does.

## Calling, hardware and memory contracts

The registry states inputs, outputs, register/flag clobbers, interrupt behavior,
memory ownership, symbol dependencies and reuse limits for each public boundary.
All APIs are non-reentrant foreground code unless explicitly documented otherwise.
Callers save AF/flags, BC, DE, HL, IX and IY unless a specific entry makes a
stronger preservation promise. Returning entries retain balanced SP behavior;
menu/round/death tail transitions can enter the state machine instead of returning
immediately. IRQ code must preserve live mappings/registers and must not race
VDP or PSG transactions. Source separation does not add interrupt masking.

Important concrete exceptions:

- `GamePacketFast_Transfer`: B=1..255, C=data port, HL=source; returns B=0,
  HL+=length, C/DE/IX/IY/IFF unchanged. AF/flags are scratch. B=0 is not allowed.
- `GameSession_MapPage`: A=map index 0/1, HL preserved, AF scratch. RestorePage0
  clobbers AF. CopyMap consumes A=ROM bank and C=RAM segment, copies exactly
  16 KiB and restores main Page0; AF/BC/DE/HL are scratch. PatchObject consumes
  B/C=top-left and IY=nine IDs; IY advances nine, C advances three, IX is preserved.
- `register`: A=value, B=VDP register; AF scratch, IFF unchanged. Serialize its
  control-latch pair externally. `stage_wait_command` returns EI and R15=0;
  it does not preserve an incoming DI state and is not an active-frame service.
- `GamePattern_Address`: HL=virtual pattern/color offset in the established
  0/4000 convention, `pattern_back` selects one of eight 16 KiB sets. HL and
  DE/IX/IY are unchanged; AF/C are scratch. It returns EI, not the caller's IFF.
- Sprites require `Init -> (Prepare -> Commit)*`. Init is DI/display-off;
  Prepare preserves IFF and writes only inactive patterns; Commit is called DI
  in blanking. The caller owns R1 16x16/unmagnified, R18=0, next R23=cy and the
  palette OR relationships. Actors C800..C82F, caches C840..C8C1 and scratch
  C980..CD6A must not overlap other live data. HUD slots 0..13 remain separate.
- First-stage `GameAudio_Tick` takes A=current Page2 bank and restores it.
  Full-session `GameAudio_Tick` derives elapsed ticks from clock state and, when
  it runs the worker, restores the native bank. Their event IDs differ. Shared
  public label names do not make these two audio ABIs interchangeable.
- Full-session renderer state uses the existing eight packed sets; the
  first-stage uses four 32 KiB sets. Names remain double buffered. Cold UI/popup
  scratch aliases are valid only in their documented modes. Video restoration
  invalidates old UI/popup state before active rendering.

Constants are assembly-time host bindings. They allocate no bytes by themselves.
The existing owner files remain authoritative for all offsets; the registry is
not an independent allocator. Another project may supply compatible aliases and
generated assets, but changing geometry, native entry points, palette, VRAM
layout or IRQ policy requires its own integration tests. Reuse in another port
has not been demonstrated by this extraction.

## Minimal reuse examples

The transfer primitive can be assembled without native game symbols or assets:

```asm
    ORG $4000
    ; Existing host code sets a valid VDP write address and source bank.
    ; Existing call site provides B=count (1..255), C=$98, HL=source.
    INCLUDE "modules/vdp/transfers.inc"
```

The mapper mechanism can use another host's RAM aliases without linking the
native simulation. The host initializes these bytes and owns their segments:

```asm
GameSession_MainSegment EQU $d010
GameSession_MapSegments EQU $d020 ; two segment IDs
    ; Include in fixed resident code, never in the Page0 segment being swapped.
    INCLUDE "modules/mapper/page0.inc"
```

To use a complete current profile, retain the existing build composition and
generated resource pipeline. Public facades reference implementations relative
to their source location; preserve the `modules/` directory hierarchy. The build
copies authored includes into the assembly directory and emits each selected
implementation once. Generated `game-host.inc`, bank tables and resource binaries
are supplied by the host pipeline, not duplicated inside the modules.

## Mandatory extraction gate

```sh
make build MAPPER=1
make verify-module-layout MAPPER=1
make test-experiments MAPPER=1
```

`verify-module-layout` checks the complete cartridge hash/size and a canonical
digest of every assembler symbol, including non-emitted RAM aliases. It also
requires declared exports and symbol dependencies to resolve. The baseline was
captured after the lossless ROM packing and before this extraction; the preserved
128 KiB profile remains **2,048,000 bytes**, SHA-256
`b80c7b72ace0ee0e9686127a156249d3cceaa3292ddea767ad1497950badbfb1`.
The guard rejects even a same-size opcode change or a changed EQU memory address.
Intentional future behavior/layout changes need a separately reviewed baseline;
do not regenerate fingerprints merely to make this structural gate pass.

The frozen matrix covers default, test, classic HUD, no hardware check and the
three-enemy first-stage profile. The independent legacy ROM is compared separately.
Additional flag combinations need their own accepted baseline before claiming
the same verified coverage. ROM identity proves that this extraction introduces
no instruction, branch, stack, bank/VDP transaction, allocation or wait change
under matching inputs/configuration. It is stronger than an FPS tolerance.

The default build uses the functional [64 KiB adapter](../../../docs/ram64-variant.md),
whose changed storage/motion implementation is outside this frozen extraction
proof. Its API and memory lifetimes are documented separately. The module gate
always checks the matching preserved 128 KiB counterpart; it does not certify
that a 64 KiB image has identical bytes or symbols.

Use [docs/cycle-budget.xlsx](../../../docs/cycle-budget.xlsx) for current
ROM-bound measurements and both RAM profiles. General gameplay/perceptual and
physical-cartridge acceptance remain separate from the zero-delta structural proof.
