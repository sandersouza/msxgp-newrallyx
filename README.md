# New Rally-X for MSX2+

Port workspace for New Rally-X. Original game data belongs only in the ignored
`references/` directories and is never downloaded by project setup.

Prepare the macOS development environment from the repository root:

```sh
make environment
```

This prepares Python/Pillow, the pinned local sjasmplus cross-assembler,
z80dasm, MAME, openMSX, ShellCheck and the native build prerequisites. It verifies
a synthetic MSX cartridge's bytes, symbols, listing and disassembly. It does not
build the game or download game/BIOS ROMs.

Preview changes or verify an existing environment:

```sh
make environment-dry-run
make environment-check
```

Setup detects the operating system. macOS is implemented; Linux and Windows are
identified and reported as unsupported pending their own implementations.

See [environment setup](docs/setup.md) for prerequisites, dependencies, recovery,
validation results, tool paths and the cross-assembly smoke test.
