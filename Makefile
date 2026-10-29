.DEFAULT_GOAL := build
.PHONY: environment environment-check extract-graphics capture-scenes analyze-scenes prepare-scenes build run checkpoints test clean build-experiments run-experiments test-experiments profile-experiments profile-movement-experiments

PYTHON ?= .venv/bin/python
# Select the presenter at build time. Both spellings are public aliases.
LEGACY ?= $(if $(legacy),$(legacy),0)
TEST_MODE ?= 0
ROM ?= $(if $(filter 1,$(LEGACY)),references/build/newrallyx.rom,$(FULL_SESSION_BUNDLE)/fixed-hud.rom)
CHECKPOINT ?=
LATEST ?= 0
NO_HUD ?= 0
PLAYER_BLITTER ?= 0
RADAR_BLITTER ?= 0
SPRITE_FLICKER ?= 0
OUTLINE_FLICKER ?= 0
FLICKER_STRESS ?= 0
HZ ?=
NATIVE ?= 0
STAGE ?= 12
FULL_GAME ?= 1
AUDIO ?= 1
FLAG_POPUPS ?= 1
ifeq ($(LEGACY),1)
ifneq ($(TEST_MODE),0)
$(error TEST_MODE is supported by the optimized presenter; use make run TEST_MODE=1 without LEGACY)
endif
endif
ENEMIES ?=
GRAPHICS_INPUT ?= references/roms/nrallyx
GRAPHICS_OUTPUT ?= references/assets/nrallyx
OVERWRITE ?= 0
SCENES_CAPTURE ?= references/scenes/review-fixed-v3
SCENES_NORMAL ?= references/scenes/rom-input/normal
SCENES_OVERLAP ?= references/scenes/rom-input/overlap

environment:
	@bash scripts/setup.sh

environment-check:
	@bash scripts/setup.sh --check

extract-graphics:
	@$(PYTHON) -B scripts/extract_graphics.py --input "$(GRAPHICS_INPUT)" --output "$(GRAPHICS_OUTPUT)" $(if $(filter 1,$(OVERWRITE)),--overwrite)

capture-scenes:
	@$(PYTHON) -B scripts/arcade_scene.py capture --assets "$(GRAPHICS_OUTPUT)" --output "$(SCENES_CAPTURE)" $(if $(filter 1,$(OVERWRITE)),--overwrite)

analyze-scenes:
	@$(PYTHON) -B scripts/arcade_scene.py analyze --assets "$(GRAPHICS_OUTPUT)" --capture "$(SCENES_CAPTURE)/frame-02200" --output "$(SCENES_NORMAL)" $(if $(filter 1,$(OVERWRITE)),--overwrite)
	@$(PYTHON) -B scripts/arcade_scene.py analyze --assets "$(GRAPHICS_OUTPUT)" --capture "$(SCENES_CAPTURE)/frame-02760" --output "$(SCENES_OVERLAP)" $(if $(filter 1,$(OVERWRITE)),--overwrite)

prepare-scenes: capture-scenes
	@$(MAKE) analyze-scenes

ifeq ($(LEGACY),1)
build: build-legacy
else
build: build-full-session
endif

build-legacy:
	@$(PYTHON) -B scripts/project.py build $(if $(filter 0,$(FLAG_POPUPS)),--no-flag-popups) $(if $(and $(filter 1,$(FULL_GAME)),$(filter 12,$(STAGE)),$(filter 0,$(NO_HUD)),$(filter 0,$(NATIVE)),$(if $(strip $(ENEMIES)),,yes)),--full-game $(if $(filter 1,$(AUDIO)),--audio)) $(if $(filter 1,$(NO_HUD)),--no-hud) $(if $(filter 1,$(NATIVE)),--native) $(if $(filter 1,$(PLAYER_BLITTER)),--player-blitter) $(if $(filter 1,$(RADAR_BLITTER)),--radar-blitter) $(if $(filter 1,$(SPRITE_FLICKER)),--sprite-flicker) $(if $(filter 1,$(OUTLINE_FLICKER)),--outline-flicker) $(if $(filter 1,$(FLICKER_STRESS)),--flicker-stress) $(if $(strip $(HZ)),--hz "$(HZ)") --stage "$(STAGE)" $(if $(strip $(ENEMIES)),--enemies "$(ENEMIES)")

run:
ifeq ($(LATEST),1)
	@$(PYTHON) -B scripts/project.py run --latest $(if $(strip $(CHECKPOINT)),--checkpoint "$(CHECKPOINT)") $(if $(filter command line,$(origin ROM)),--rom "$(ROM)")
else
ifneq ($(strip $(CHECKPOINT)),)
	@$(PYTHON) -B scripts/project.py run --checkpoint "$(CHECKPOINT)"
else
ifneq ($(origin ROM),command line)
run: build
endif
	@$(PYTHON) -B scripts/project.py run --rom "$(ROM)"
endif
endif

checkpoints:
	@$(PYTHON) -B scripts/project.py checkpoints


test:
	@$(PYTHON) -B -m unittest discover -s tests -v

clean:
	@python3 -B scripts/clean.py

# Historical experiment aliases remain supported; SCREEN5 uses LEGACY=1.
-include experiments/fixed-hud/targets.mk
