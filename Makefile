# Makefile

SHELL  := /bin/bash
PYTHON := python3

UNIT_MODULES :=  \
    crc_engine   \
    crc_checker  \
    scrambler    \
    qam_mapper   \
    qam_demapper \
    cp_inserter  \
    cp_remover

COVERAGE_MERGED := sim/coverage_merged.dat
COVERAGE_INFO   := sim/coverage.info
COVERAGE_HTML   := sim/coverage_html

# Logging
_LOG_DIR  := logs
_LOG_FILE  = $(_LOG_DIR)/$(firstword $(MAKECMDGOALS)).log

ifneq ($(_LOGGED),1)

.PHONY: $(MAKECMDGOALS)
$(MAKECMDGOALS):
	@mkdir -p $(_LOG_DIR)
	+unbuffer -p $(MAKE) $@ _LOGGED=1 2>&1 | tee >(sed 's/\x1b\[[0-9;]*m//g' > $(_LOG_FILE))
else
# real targets, only reached on re-invocation with _LOGGED=1

# Phony targets
.PHONY: help setup \
        sim unit-sim integration-sim \
        $(addprefix sim-,$(UNIT_MODULES)) \
        coverage coverage-serve test lint \
		format waves clean clean-sim \
		clean-tools

# Help
help:
	@echo ""
	@echo "Usage: make <target> [MODULE=<module>]"
	@echo ""
	@echo "Setup"
	@echo "  setup              First-time bootstrap (after direnv allow)"
	@echo ""
	@echo "Simulation"
	@echo "  unit-sim           Run all 7 unit TBs via cocotb/Verilator"
	@echo "  integration-sim    Run nr_chain loopback TB (needs unit-sim)"
	@echo "  sim                unit-sim + integration-sim"
	@echo "  sim-<module>       Run a single unit TB  e.g. make sim-crc_engine"
	@echo ""
	@echo "Python tests"
	@echo "  test               pytest verif/common/tests/ (no simulator)"
	@echo ""
	@echo "Waveforms"
	@echo "  waves MODULE=<m>   Sim with FST dump + open GTKWave"
	@echo "                     e.g. make waves MODULE=crc_engine"
	@echo ""
	@echo "Quality"
	@echo "  lint               pre-commit run --all-files"
	@echo "  format             Verible (SV) + ruff (Python) in-place"
	@echo ""
	@echo "Clean"
	@echo "  clean              All build/cache artifacts"
	@echo "  clean-sim          Simulation artifacts only"
	@echo "  clean-tools        Remove .tools/ (re-run setup to restore)"
	@echo ""
	@echo "Modules: $(UNIT_MODULES)"
	@echo ""

# Setup
setup:
	@bash scripts/setup.sh

# Simulation

# Per-module shortcut: make sim-crc_engine, make sim-scrambler, ...
$(addprefix sim-,$(UNIT_MODULES)):
	$(MAKE) -C sim/$(@:sim-%=%)

unit-sim: $(addprefix sim-,$(UNIT_MODULES))

integration-sim:
	$(MAKE) -C sim/nr_chain

sim: unit-sim integration-sim coverage

coverage:
	@echo "-> Merging coverage data..."
	@verilator_coverage --write $(COVERAGE_MERGED) \
	    $(shell find sim -name "coverage.dat")
	@echo "-> Writing lcov info..."
	@verilator_coverage --write-info $(COVERAGE_INFO) $(COVERAGE_MERGED)
	@if command -v genhtml >/dev/null 2>&1; then \
	    genhtml \
	        --title "fpga-cicd-toolchain-demo" \
	        --branch-coverage \
	        --function-coverage \
	        --show-details \
			--exclude "*/sim/*" \
	        --output-directory $(COVERAGE_HTML) \
	        $(COVERAGE_INFO); \
	    echo "-> HTML report: $(COVERAGE_HTML)/index.html"; \
	else \
	    echo "-> genhtml not found: sudo apt-get install -y lcov"; \
	fi

coverage-serve:
	@echo "-> Serving coverage report at http://localhost:8080"
	@echo "-> VS Code: Ports tab will auto-forward"
	@echo "-> Ctrl+C to stop"
	python3 -m http.server 8080 --directory $(COVERAGE_HTML)

# Python tests (no simulator)
test:
	pytest verif/common/tests/

# Waveforms
waves:
	@[ -n "$(MODULE)" ] || \
	    { echo "Usage: make waves MODULE=<module>"; \
	      echo "Modules: $(UNIT_MODULES) nr_chain"; exit 1; }
	$(MAKE) -C sim/$(MODULE) waves
	@if command -v gtkwave >/dev/null 2>&1; then \
	    gtkwave sim/$(MODULE)/sim_build/dump.fst & \
	elif command -v surfer >/dev/null 2>&1; then \
	    surfer sim/$(MODULE)/sim_build/dump.fst & \
	else \
	    echo "No waveform viewer found."; \
	    echo "  gtkwave:          sudo apt-get install -y gtkwave"; \
	    echo "  surfer (modern):  cargo install --git https://gitlab.com/surfer-project/surfer surfer"; \
	fi

# Lint
lint:
	pre-commit run --all-files

# Format
format:
	@echo "-> Verible: formatting SystemVerilog..."
	@find rtl/ -name '*.sv' -o -name '*.v' | xargs -r \
		.tools/verible/bin/verible-verilog-format \
		--inplace \
		--indentation_spaces=4 \
		--column_limit=100
	@echo "-> ruff: formatting Python..."
	ruff check --fix .
	ruff format .

# Clean
clean: clean-sim
	find . -type d -name '__pycache__'  -exec rm -rf {} +
	find . -type f -name '*.pyc'        -delete
	find . -type d -name '*.egg-info'   -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.mypy_cache'  -exec rm -rf {} +
	find . -type d -name '.ruff_cache'  -exec rm -rf {} +
	find . -type f -name 'results.xml'  -delete

clean-sim:
	@for m in $(UNIT_MODULES) nr_chain; do \
		$(MAKE) -C sim/$$m clean --no-print-directory 2>/dev/null || true; \
	done
	rm -f $(COVERAGE_MERGED) $(COVERAGE_INFO)
	rm -rf $(COVERAGE_HTML)

clean-tools:
	rm -rf .tools/

endif
