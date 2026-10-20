# Execution ledger — plan: 2026-10-20-macos-bootstrap.md

- Approved by user on 2026-10-20 for execution in this conversation.
- Pre-flight: Task 1 Make targets forward flags consumed by Task 2 macOS script;
  Task 3 documents those same flags and Python contract. Interfaces are aligned.
- Ruling: work in the current checkout on dedicated branch
  `chore/2-macos-bootstrap`, preserving existing user changes — the approved plan
  specifies this branch and local files — isolation is by branch, not worktree.
- Ruling: use a small Python verification helper in addition to Bash — checking
  actual interpreter identity/imports reliably requires Python — one extra file.
- Ruling: retain this ledger with the plan and leave all work uncommitted — the
  approved delivery plan prohibits commits/push without separate authorization.
- Task 1: complete; dispatcher and Make tests observed RED then GREEN (5 tests).
- Task 2: code implemented; macOS shell tests and real Python helper tests observed
  RED then GREEN. Stock Bash 3.2 exposed nounset/empty-array iteration; guarded
  iterations fixed it. An added regression caught installed versions being skipped
  by preview/early check; version validation now precedes those early returns.
- Verification: 21 tests pass; Bash syntax passes; real dry-run passes.
- Host setup and retry created/reused .venv but cannot install Pillow under the
  current network restriction. Real Pillow import/PNG round trip and successful
  no-op rerun remain unverified. ShellCheck unavailable.
- Project board checked through browser: issue #2 is already In progress.
- Task 3: documentation and validation evidence written; independent review performed.
- Final: fixed existing-venv validation skipped when Homebrew Python is absent —
  regression observed RED then GREEN, suite 21/21.
- Ruling: when the base Python is missing, conservatively refuse to trust an
  existing .venv before any installation — base compatibility cannot be established
  — manual base restoration or moving the preserved environment is required.
- Final: minor (deferred): standard Homebrew fallback locations lack isolated
  automated coverage; custom-prefix discovery through PATH is tested.
- No original game data added; no commit, push, PR, merge or issue closure performed.
- GitHub issue description updated through the browser after the connector returned
  HTTP 403. Re-fetched through the read connector and synchronized the local draft.
- Delivery stays local on the dedicated branch; integration is not ready while
  real host dependency validation and static analysis remain pending.

## Full toolchain expansion — user approved

- User approved the explicit tool table and byte-level assembly smoke proposal;
  this extends the existing bootstrap flow. No new approval or chat is required.
- Required packages: z80dasm, MAME, openMSX, ShellCheck, alongside Python/Git/GH.
- Added local sjasmplus installer pinned by version and verified upstream commit,
  building without optional Lua; no system installation or PATH substitution.
- Added synthetic cartridge, exact byte verification, symbol/listing checks,
  disassembly and input/output-hash evidence caching. Check/dry-run remain read-only.
- TDD: new toolchain unit/integration tests observed RED before implementation;
  regression tests caught z80dasm's broken long version option and multiline
  tool banners hiding their actual version. Both were corrected.
- Real z80dasm successfully disassembled synthetic instructions. Native source
  compilation, actual sjasmplus assembly, emulator execution and real ShellCheck
  remain unverified: managed session denied brew writes during openMSX installation.
- Latest host inspection: Homebrew7.0.10, GH2.102.0, Clang21.0.0; other observed
  platform details remain in docs/setup.md. Earlier version evidence is historical.
- Independent review requested for the complete expansion; no commit/push.
- Expansion review: removed xcrun/developer shims from internal tool lookup after
  the reviewer reproduced external cache writes. Regression observed RED then
  GREEN with direct selected-developer paths.
- Expansion review: corrected corrupt smoke-cache preview to report the same
  preservation blocker as install; regression observed RED before the fix.
- Scope decision: treat preview/recovery inconsistency as acceptance-relevant,
  despite its initial minor review label, because dry-run must identify blockers.
- Final expanded suite: 38/38 passed, including real z80dasm on synthetic code.
  Bash syntax and git diff whitespace checks passed. Both review fixes have
  dedicated regressions observed RED then GREEN; no second review was required.
- Project Estimate updated to 16 hours for the expanded scope; issue remains
  In progress / P2 / Size M. Local Markdown was used to publish the updated scope
  and evidence. Real provisioning remains blocked by managed Homebrew write access.

## Real ShellCheck follow-up

- User's local setup installed ShellCheck and exposed SC1007 on three empty
  CDPATH assignments. Reproduced with the actual executable (exit 1).
- Changed those assignments to explicit `CDPATH=''`, preserving directory
  resolution behavior without suppressing the diagnostics.
- Actual ShellCheck and Bash syntax checks now pass; the remaining toolchain
  installation/readiness is verified separately from this static-analysis fix.

## Resumed host validation — 2026-10-20

- Read AGENTS.md, setup documentation, this ledger, the approved plan, issue #2
  and the personal vault's required baseline/GitHub/Python guidelines. Kept the
  current checkout and all prior local changes on `chore/2-macos-bootstrap`.
- Initial check: openMSX 21.0 and ShellCheck 0.11.0 are installed; local sjasmplus
  was absent. Dry-run passed. The existing .venv already contains Pillow 13.0.0.
- Real setup reached native compilation, then failed on missing `cassert`.
  Investigation showed direct Clang omitted the SDK whereas the developer shim
  selected it. The header exists in the installed macOS SDK; an explicit SDK
  compile probe passed. No Command Line Tools reinstall was necessary.
- Ruling: derive and export SDKROOT from the selected developer installation,
  replacing inherited SDKROOT — keeps compiler/SDK aligned and avoids xcrun's
  external cache writes — custom SDK overrides require a future explicit contract.
- Fixed SDK selection in macos.sh. Three regressions observed RED then GREEN:
  native CLT build, full Xcode layout, missing SDK refusal in all modes.
- Real `make environment` passed: pinned sjasmplus 1.24.0 compiled, exact-byte
  synthetic assembly/symbol/listing/disassembly passed, Pillow 13.0.0 imported,
  pip 26.2.1 check found no broken requirements.
- Real check, dry-run and second setup all passed. SHA-256/symlink-target/file-mtime
  snapshots of .venv and .tools were unchanged for each command. PNG round trip
  passed using the local isolated interpreter.
- Final validation: 41/41 tests, real ShellCheck, Bash syntax and whitespace checks
  passed. Managed tools, Python environment and reference data remain ignored.
- Previous independent expansion review remains recorded above; this follow-up
  fixes the native-build gap with regression coverage and real host verification.
  Deferred minor remains: standard Homebrew fallback paths lack isolated tests.
- No commit, push, PR, merge or issue closure; delivery remains local pending
  separate authorization. Intel/other macOS hosts and emulator boots are unverified.
- Published the updated local issue draft with real validation evidence and checked
  that the remote body matches it (apart from gh's trailing newline). GitHub CLI
  cannot read Projects with the current token (missing read:project); used the
  authenticated browser instead. Verified issue #2 moved to In review with
  Priority P2, Size M and Estimate 16; unrelated issue #1 remains in Backlog.
