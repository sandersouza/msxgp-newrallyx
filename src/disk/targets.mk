.PHONY: build-disk verify-disk
build-disk: build
	@$(PYTHON) -B scripts/disk_package.py

verify-disk: build-disk
	@$(PYTHON) -B scripts/verify_disk.py --mode basic
	@$(PYTHON) -B scripts/verify_disk.py --mode dos

.PHONY: build-megaram verify-megaram
build-megaram: build
	@$(PYTHON) -B scripts/compact_game_build.py --backend megaram --fixed-ram --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B scripts/megaram_package.py --fixed-ram --publish

verify-megaram: build-megaram
	@$(PYTHON) -B scripts/compact_game_verify.py --fixed-ram --ram-kind plain --mode dos --size 768
	@$(PYTHON) -B scripts/compact_game_verify.py --fixed-ram --ram-kind plain --mode basic --size 768
	@$(PYTHON) -B scripts/compact_game_verify.py --fixed-ram --ram-kind plain --mode basic --size 768 --topology shared
	@$(PYTHON) -B scripts/compact_game_verify.py --fixed-ram --ram-kind plain --mode basic --size 512
