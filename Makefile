.PHONY: environment environment-check environment-dry-run extract-graphics
.DEFAULT_GOAL := environment
.PHONY: capture-scene reconstruct-scene preview-scene analyze-scene

GRAPHICS_INPUT ?= references/roms/nrallyx
GRAPHICS_OUTPUT ?= references/assets/nrallyx
OVERWRITE ?= 0
SCENE_OUTPUT ?= references/scenes/capture
SCENE_INPUT ?= references/scenes/capture/frame-02200
SCENE_REPORT ?= references/scenes/report
SCENE_FRAMES ?= 2200 2410 2411 2760 2761
SCENE_LAYOUT ?= compact
ROM_NORMAL ?= references/scenes/rom-input/normal
ROM_OVERLAP ?= references/scenes/rom-input/overlap
ROM_OUTPUT ?= references/build/screen5
ROM ?= $(ROM_OUTPUT)/static-scene.rom
MSX_MACHINE ?= Panasonic_FS-A1WSX
MSX_BIOS ?= references/msxbios
OPENMSX ?= openmsx
SJASMPLUS ?= .tools/sjasmplus/1.24.0/sjasmplus

.PHONY: rom run verify-rom
rom:
	@.venv/bin/python -B scripts/msx_rom.py build --normal "$(ROM_NORMAL)" --overlap "$(ROM_OVERLAP)" --output "$(ROM_OUTPUT)" --assembler "$(SJASMPLUS)"

run:
	@.venv/bin/python -B scripts/msx_rom.py run --rom "$(ROM)" --machine "$(MSX_MACHINE)" --bios "$(MSX_BIOS)" --openmsx "$(OPENMSX)" --output "$(ROM_OUTPUT)/run"

verify-rom:
	@.venv/bin/python -B scripts/msx_rom.py verify --rom "$(ROM)" --machine "$(MSX_MACHINE)" --bios "$(MSX_BIOS)" --openmsx "$(OPENMSX)" --output "$(ROM_OUTPUT)/verification"

environment:
	@bash scripts/setup.sh

environment-check:
	@bash scripts/setup.sh --check

environment-dry-run:
	@bash scripts/setup.sh --dry-run

extract-graphics:
	@.venv/bin/python -B scripts/extract_graphics.py --input "$(GRAPHICS_INPUT)" --output "$(GRAPHICS_OUTPUT)" $(if $(filter 1,$(OVERWRITE)),--overwrite)

capture-scene:
	@.venv/bin/python -B scripts/arcade_scene.py capture --assets "$(GRAPHICS_OUTPUT)" --output "$(SCENE_OUTPUT)" --frames $(SCENE_FRAMES)

reconstruct-scene:
	@.venv/bin/python -B scripts/arcade_scene.py reconstruct --assets "$(GRAPHICS_OUTPUT)" --capture "$(SCENE_INPUT)" --output "$(SCENE_REPORT)"

preview-scene:
	@.venv/bin/python -B scripts/arcade_scene.py preview --assets "$(GRAPHICS_OUTPUT)" --capture "$(SCENE_INPUT)" --output "$(SCENE_REPORT)" --layout "$(SCENE_LAYOUT)"

analyze-scene:
	@.venv/bin/python -B scripts/arcade_scene.py analyze --assets "$(GRAPHICS_OUTPUT)" --capture "$(SCENE_INPUT)" --output "$(SCENE_REPORT)" --layout "$(SCENE_LAYOUT)"
