# macOS Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after user review.

**Goal:** Make `make environment` prepare the macOS extraction environment and identify other operating systems for future implementations.

**Architecture:** A Makefile delegates to a Bash OS dispatcher, which invokes a separate macOS implementation. Brewfile and pinned Python requirements define the environment; checks and previews remain read-only.

**Tech Stack:** GNU Make, Bash 3.2, Homebrew, Python 3.14, Pillow, Python unittest, ShellCheck.

**Spec:** `docs/superpowers/specs/2026-10-20-macos-bootstrap-design.md`

## Global Constraints

- Support native Apple Silicon and Intel macOS installations using stock Bash 3.2.
- Use Python 3.14; pin Pillow exactly after verifying release metadata and macOS wheels.
- Never run sudo or a downloaded installation script.
- Never silently replace an incompatible or broken `.venv`.
- Check-only and preview perform no installations or file mutations, including bytecode and Homebrew cache writes.
- Do not download ROMs/BIOS, authenticate GitHub, upgrade installed formulae unconditionally, or alter unrelated user work.
- Only macOS is implemented; detect Linux, Windows and unknown OS and explain the support boundary.
- Do not commit, push, or close the issue without applicable authorization.

## Review Focus

- Invocation outside the repository or from a path containing spaces must resolve files correctly.
- A broken or foreign `.venv` must produce recovery instructions without replacement.
- Homebrew unavailable on PATH must be discovered by platform location without assuming one prefix.
- Read-only checks must not generate Python bytecode or trigger Homebrew updates/downloads.
- Windows shell identifiers and WSL must not dispatch to the macOS implementation.

---

### Task 1: Public command and platform dispatch

**Files:** `Makefile`, `scripts/setup.sh`, `tests/test_setup.py`.

**Interfaces:** Make targets `environment`, `environment-check`, and `environment-dry-run` invoke `bash scripts/setup.sh` with no flag, `--check`, and `--dry-run`, respectively. Dispatcher validates arguments, reports OS, and invokes `scripts/environment/macos.sh` only for Darwin. Exit codes: 0 success/help/valid preview, 1 unmet requirements or unsupported platform, 2 invalid usage, 3 incompatible environment, 4 installation/verification failure. Make may wrap a child failure in its own exit status.

- [ ] Write unittest cases using temporary repositories and executable stubs for Darwin, Linux, MINGW/MSYS/CYGWIN, Windows_NT, unknown OS, help and invalid arguments. Assert unsupported platforms invoke no installer; WSL follows Linux behavior.
- [ ] Run `python3 -B -m unittest discover -s tests -v`; confirm failures identify the missing dispatcher.
- [ ] Implement the three Make targets and Bash 3.2 dispatcher, preserving argument quoting and resolving the repository from the script location.
- [ ] Run tests including invocation from another working directory and a repository path containing spaces; assert all dispatch outcomes and Make target arguments.

### Task 2: Safe macOS environment provisioning

**Files:** `scripts/environment/macos.sh`, `Brewfile`, `requirements.txt`, `.gitignore`, `tests/test_setup.py`.

**Interfaces:** macOS implementation accepts the same mode flag, uses repository `.venv/bin/python`, and returns Task 1 exit codes. Required formulae are `python@3.14`, `git`, `gh`. Dependency version inspection and image imports use the local interpreter with bytecode disabled.

- [ ] Verify exact Pillow release metadata, Python 3.14 support and both macOS wheel architectures from official sources; write the resulting exact pin in requirements.txt. Verify sjasmplus/openMSX official macOS installation and CLI references; leave them outside required setup.
- [ ] Add failing tests for missing CLT/Homebrew, both Homebrew prefix layouts, unsupported CPU, Rosetta mismatch, missing packages, pip/install failure, existing incompatible/foreign/broken venv, reuse, and no-op repeat setup. Use synthetic fixtures and controlled executable paths.
- [ ] Run the tests and confirm meaningful failures before implementation.
- [ ] Implement manual prerequisite guidance; install only missing Brewfile formulae with auto-update/analytics disabled; resolve Python from Homebrew; validate or create `.venv`; install only when the pinned Pillow check is unmet. Never invoke global pip or replace an existing incompatible path.
- [ ] Add `.venv/`, Python bytecode/cache exclusions while retaining current user ignore rules and reference protection.
- [ ] Test check and preview using filesystem snapshots and command logs: no files changed, no installing commands, no network/cache-writing brew calls. Check must fail for missing requirements; preview must describe required changes and manual blockers.
- [ ] Run `bash -n scripts/setup.sh scripts/environment/macos.sh`, ShellCheck when available, and the complete unittest suite. Resolve failures before host validation.

### Task 3: Host validation, documentation and tracking

**Files:** `README.md`, `docs/setup.md`, `.github/issues/bootstrap-macos-homebrew.md`.

**Interfaces:** Document the Make targets as primary commands and `.venv/bin/python` as the Python contract for issue #1. Documentation must distinguish actual host tests from simulated coverage.

- [ ] At implementation start, create/reuse `chore/2-macos-bootstrap`; move only issue #2 to In Progress when project write access is available. If blocked, report the exact limitation without changing unrelated items.
- [ ] Run `make environment-dry-run`, `make environment`, `make environment-check`, and `make environment` again on the host. Record mutations/version outcomes; if sandbox/network restrictions block installation, record it as unverified and provide the exact local command needed.
- [ ] Verify Pillow import/version, `pip check`, and a synthetic in-memory PNG round trip with `.venv/bin/python -B`. Confirm ignored environment/cache/reference paths with `git check-ignore` and inspect `git diff --check` and status.
- [ ] Document setup, prerequisite official links, authentication as separate manual `gh auth login`, dependency update policy, missing/broken environments, install failures, OS routing, optional toolchain decisions, and actual macOS arm64 coverage. Mark Intel, other macOS releases, Linux and Windows as unverified or unsupported as appropriate.
- [ ] Review the final changes against every acceptance criterion. Align the local issue draft with actual progress and evidence; leave incomplete items unchecked. Use the review project status only when delivery is ready for review and access permits. Report validation and blockers without claiming completion of blocked checks.

## Plan review

Self-review: the three tasks cover the spec's public interface, provisioning,
failure behavior, dependency contract, optional toolchain boundary, documentation
and tracking. All five review-focus cases have explicit owning tests above.
Recommended execution: inline in the current conversation; these components are
small and share one setup contract. No commit, push or merge is planned.
