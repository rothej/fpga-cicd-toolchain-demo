# Makefile

#  Config
PYTHON        := python3
SIM           := verilator
TOPLEVEL_LANG := verilog
SIM_BUILD     := sim_build
RESULTS       := results.xml
WAVES_FILE    := $(SIM_BUILD)/dump.fst

#  Phony targets
.PHONY: help setup sim test lint format waves clean clean-sim clean-tools

#  Help
help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "  setup        First-time bootstrap (after direnv allow)"
	@echo "  sim          Run cocotb simulation via pytest"
	@echo "  test         Alias for sim"
	@echo "  lint         Run all linters (pre-commit + Verible)"
	@echo "  format       Auto-format SV files with Verible + Python files with black/isort"
	@echo "  waves        Run sim then open FST dump in GTKWave"
	@echo "  clean        Remove all build/sim/cache artifacts"
	@echo "  clean-sim    Remove only simulation artifacts"
	@echo "  clean-tools  Remove installed tools (.tools/)"
	@echo ""

#  Setup
setup:
	@bash scripts/setup.sh

#  Simulation / Tests
sim:
	SIM=$(SIM) TOPLEVEL_LANG=$(TOPLEVEL_LANG) pytest -v --tb=short

test: sim

#  Waveforms
waves: sim
	@command -v gtkwave >/dev/null 2>&1 || \
		{ echo "gtkwave not found: sudo apt-get install -y gtkwave"; exit 1; }
	gtkwave $(WAVES_FILE) &

#  Lint
lint:
	pre-commit run --all-files

#  Format
format:
	@echo "Formatting SystemVerilog files..."
	@find rtl/ -name '*.sv' -o -name '*.v' | xargs -r \
		.tools/verible/bin/verible-verilog-format \
		--inplace \
		--indentation_spaces=4 \
		--column_limit=100
	@echo "Formatting Python files..."
	black .
	isort .

#  Clean
clean: clean-sim
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -exec rm -rf {} +
	find . -type f -name '$(RESULTS)' -delete

clean-sim:
	rm -rf $(SIM_BUILD)
	find . -name '*.vcd' -delete
	find . -name '*.fst' -delete
	find . -name '*.fst.hier' -delete

clean-tools:
	rm -rf .tools/
