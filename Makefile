.PHONY: environment environment-check environment-dry-run

environment:
	@bash scripts/setup.sh

environment-check:
	@bash scripts/setup.sh --check

environment-dry-run:
	@bash scripts/setup.sh --dry-run
