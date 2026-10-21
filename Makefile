.DEFAULT_GOAL := build
.PHONY: environment environment-check build run test clean

PYTHON ?= .venv/bin/python

environment:
	@bash scripts/setup.sh

environment-check:
	@bash scripts/setup.sh --check

build:
	@$(PYTHON) -B scripts/project.py build

run:
	@if [ ! -f references/build/newrallyx.rom ]; then $(MAKE) build; fi
	@$(PYTHON) -B scripts/project.py run

test:
	@$(PYTHON) -B -m unittest discover -s tests -v

clean:
	@python3 -B scripts/clean.py
