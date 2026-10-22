.DEFAULT_GOAL := build
.PHONY: environment environment-check extract-graphics capture-scenes analyze-scenes prepare-scenes build run test clean

PYTHON ?= .venv/bin/python
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

build:
	@$(PYTHON) -B scripts/project.py build

run:
	@if [ ! -f references/build/newrallyx.rom ]; then $(MAKE) build; fi
	@$(PYTHON) -B scripts/project.py run

test:
	@$(PYTHON) -B -m unittest discover -s tests -v

clean:
	@python3 -B scripts/clean.py
