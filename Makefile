.PHONY: environment environment-check environment-dry-run extract-graphics

GRAPHICS_INPUT ?= references/roms/nrallyx
GRAPHICS_OUTPUT ?= references/assets/nrallyx
OVERWRITE ?= 0

environment:
	@bash scripts/setup.sh

environment-check:
	@bash scripts/setup.sh --check

environment-dry-run:
	@bash scripts/setup.sh --dry-run

extract-graphics:
	@.venv/bin/python -B scripts/extract_graphics.py --input "$(GRAPHICS_INPUT)" --output "$(GRAPHICS_OUTPUT)" $(if $(filter 1,$(OVERWRITE)),--overwrite)
