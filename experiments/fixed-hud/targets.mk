EXPERIMENT_ENEMIES ?= $(if $(strip $(ENEMIES)),$(ENEMIES),3)
EXPERIMENT_BUNDLE = references/experiments/stage-one$(if $(filter 1,$(EXPERIMENT_ENEMIES)),,-$(EXPERIMENT_ENEMIES)-enemies)
AUDIO_REFERENCE_REVISION ?= 6d562a791b0cc242119a31dd686ff8e93eb94fe0
TEST_MODE ?= 0
HUD_VARIANT ?= compact
MSX_LOGO ?= 1
HARDWARE_CHECK ?= 1
FULL_SESSION_BUNDLE = references/experiments/full-session$(if $(filter 1,$(TEST_MODE)),-test,)$(if $(filter classic,$(HUD_VARIANT)),-hud-classic,)$(if $(filter 0,$(MSX_LOGO)),-no-logo,)$(if $(filter 0,$(HARDWARE_CHECK)),-no-check,)

HUD_HIGH_SCORE ?= 20000
HUD_SCORE ?= 0
HUD_ROUND ?= 1
HUD_LIVES ?= 4

build-hud-lab:
	@$(PYTHON) -B experiments/fixed-hud/build.py --high-score "$(HUD_HIGH_SCORE)" --score "$(HUD_SCORE)" --round-number "$(HUD_ROUND)" --lives "$(HUD_LIVES)"

run-hud-lab: build-hud-lab
	@$(PYTHON) -B scripts/project.py run --rom references/experiments/fixed-hud/fixed-hud.rom

profile-hud-lab: build-hud-lab
	@$(PYTHON) -B experiments/fixed-hud/profile.py

profile-movement-experiments: build-hud-lab
	@$(PYTHON) -B experiments/fixed-hud/profile.py --movement

test-hud-lab: build-hud-lab
	@$(PYTHON) -B -m unittest discover -s experiments/fixed-hud -p test_hud.py
	@$(PYTHON) -B experiments/fixed-hud/verify.py
	@$(PYTHON) -B experiments/fixed-hud/analyze.py
	@$(PYTHON) -B experiments/fixed-hud/verify.py --matrix
	@$(PYTHON) -B experiments/fixed-hud/analyze.py
	@$(PYTHON) -B experiments/fixed-hud/edge_contract.py
	@$(PYTHON) -B experiments/fixed-hud/verify.py --continuous
	@$(PYTHON) -B experiments/fixed-hud/analyze.py
	@$(PYTHON) -B experiments/fixed-hud/scanout.py

.PHONY: build-first-stage run-first-stage test-first-stage profile-first-stage
build-first-stage:
	@$(PYTHON) -B experiments/fixed-hud/build.py --gameplay --enemies "$(EXPERIMENT_ENEMIES)"

run-first-stage: build-first-stage
	@$(PYTHON) -B scripts/project.py run --rom "$(EXPERIMENT_BUNDLE)/fixed-hud.rom"

test-first-stage: build-first-stage
	@$(PYTHON) -B -m unittest discover -s experiments/fixed-hud -p 'test_*.py'
	@$(PYTHON) -B experiments/fixed-hud/test_hud_programs.py --bundle "$(EXPERIMENT_BUNDLE)" --out "$(EXPERIMENT_BUNDLE)/hud-program-proof"
	@$(PYTHON) -B experiments/fixed-hud/game_verify.py --bundle "$(EXPERIMENT_BUNDLE)" --frames 240 --headless
	@$(PYTHON) -B experiments/fixed-hud/game_verify.py --bundle "$(EXPERIMENT_BUNDLE)" --scenario smoke --frames 480 --headless
	@$(PYTHON) -B experiments/fixed-hud/game_verify.py --bundle "$(EXPERIMENT_BUNDLE)" --scenario route --frames 10000 --headless

profile-first-stage: build-first-stage
	@$(PYTHON) -B experiments/fixed-hud/game_profile.py --bundle "$(EXPERIMENT_BUNDLE)" --route

# The default experiment consumes shared full-session rules with SCREEN4.
.PHONY: build-hud-lab run-hud-lab profile-hud-lab test-hud-lab
build-experiments: build-full-session
run-experiments: run-full-session
profile-experiments: profile-full-session
test-experiments: test-full-session

.PHONY: build-full-session run-full-session test-full-session profile-full-session
build-full-session: build-audio-reference
	@NRX_HARDWARE_CHECK="$(HARDWARE_CHECK)" NRX_MSX_LOGO="$(MSX_LOGO)" NRX_HUD_VARIANT="$(HUD_VARIANT)" NRX_TEST_MODE="$(TEST_MODE)" $(PYTHON) -B experiments/fixed-hud/build.py --full-session
	@$(PYTHON) -B experiments/fixed-hud/session_build.py --export "$(FULL_SESSION_BUNDLE)"

run-full-session: build-full-session
	@$(PYTHON) -B scripts/project.py run --rom "$(FULL_SESSION_BUNDLE)/fixed-hud.rom"

test-full-session: build-full-session
	@$(PYTHON) -B experiments/fixed-hud/session_boot_module_verify.py --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario controls --contracts
	@$(PYTHON) -B -m unittest discover -s experiments/fixed-hud -p 'test_*.py'
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario start --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario integration --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario two-player --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario flags --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario attract --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario radar --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --scenario smoke --contracts
	@$(PYTHON) -B experiments/fixed-hud/session_rocks_verify.py --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B experiments/fixed-hud/session_speed_verify.py --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B experiments/fixed-hud/session_steering_verify.py --bundle "$(FULL_SESSION_BUNDLE)" --frames 16000
	@$(PYTHON) -B experiments/fixed-hud/session_audio_verify.py --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B experiments/fixed-hud/session_sprite_verify.py --bundle "$(FULL_SESSION_BUNDLE)"

profile-full-session: build-full-session
	@$(PYTHON) -B experiments/fixed-hud/session_profile.py --bundle "$(FULL_SESSION_BUNDLE)"
	@$(PYTHON) -B experiments/fixed-hud/session_report.py --bundle "$(FULL_SESSION_BUNDLE)"

.PHONY: test-performance-adapters
test-performance-adapters:
	@$(PYTHON) -B experiments/fixed-hud/test_game_ring.py
	@$(PYTHON) -B experiments/fixed-hud/test_game_ring.py --fast-refresh
	@$(PYTHON) -B experiments/fixed-hud/test_game_actors.py --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_sprites.py --emulator --bios references/msxbios --optimized --out outputs/fixed-hud/sprite-clip-after
	@$(PYTHON) -B experiments/fixed-hud/test_game_radar.py --emulator --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_radar_fast.py --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_radar_fast.py --bios references/msxbios --uniform-source --out outputs/fixed-hud/radar-uniform-synthetic
	@$(PYTHON) -B experiments/fixed-hud/test_game_packet_fast.py --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_sprite_mask_fast.py --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_name_stream.py --bios references/msxbios
	@$(PYTHON) -B experiments/fixed-hud/test_game_boundary_fast.py --emulator --bios references/msxbios

.PHONY: test-render-queues
test-render-queues:
	@$(PYTHON) -B experiments/fixed-hud/game_smoke_cache.py
	@$(PYTHON) -B experiments/fixed-hud/game_dirty_probe.py

.PHONY: build-audio-reference run-audio-reference
build-audio-reference:
	@$(PYTHON) -B experiments/fixed-hud/build_profiles.py --revision "$(AUDIO_REFERENCE_REVISION)"

run-audio-reference: build-audio-reference
	@$(PYTHON) -B scripts/project.py run --rom references/experiments/audio-reference/newrallyx-audio.rom

.PHONY: test-phase-cache
test-phase-cache: build-first-stage
	@$(PYTHON) -B experiments/fixed-hud/test_hud_programs.py --bundle "$(EXPERIMENT_BUNDLE)" --out references/experiments/phase-cache-hud-proof
	@$(PYTHON) -B experiments/fixed-hud/game_phase_verify.py
	@$(PYTHON) -B experiments/fixed-hud/phase_cache_report.py
