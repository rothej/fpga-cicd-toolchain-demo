# sim/common.mk
# Shared config included by every per-module Makefile.
# Each per-module Makefile must set DUT before including this file.

REPO_ROOT  := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)
RTL_DIR    := $(REPO_ROOT)/rtl
VERIF_DIR  := $(REPO_ROOT)/verif
TOOLS_DIR  := $(REPO_ROOT)/.tools
SIM_BUILD  := sim_build
WAVES_FILE := $(SIM_BUILD)/dump.fst

# Coverage outputs, both live inside SIM_BUILD so `make clean` handles them.
COVERAGE_DAT  := $(abspath $(SIM_BUILD))/coverage.dat
COVERAGE_INFO := $(abspath $(SIM_BUILD))/coverage.info
COVERAGE_HTML := $(abspath $(SIM_BUILD))/coverage_html

SIM           := verilator
TOPLEVEL_LANG := verilog

# ---------------------------------------------------------------------------
# Verilator - local build, not system-installed
# ---------------------------------------------------------------------------
# PATH is prepended so verilator and verilator_coverage resolve to the local
# build. VERILATOR_ROOT is intentionally NOT exported: the compiled-in root
# must match the env var exactly or Verilator errors. cocotb's Makefile.verilator
# auto-detects it via `verilator -V` when left unset.

export PATH    := $(TOOLS_DIR)/verilator/bin:$(PATH)

# ---------------------------------------------------------------------------
# Python path
# ---------------------------------------------------------------------------
# REPO_ROOT on PYTHONPATH lets cocotb resolve MODULE as a dotted package path:
#   MODULE := verif.crc_engine.test_crc_engine
#   -> importlib.import_module("verif.crc_engine.test_crc_engine")
# Requires verif/__init__.py, verif/<dut>/__init__.py, and
# verif/<dut>/test/__init__.py to exist.

export PYTHONPATH := $(REPO_ROOT):$(PYTHONPATH)

# ---------------------------------------------------------------------------
# Verilator compile flags
# ---------------------------------------------------------------------------

EXTRA_ARGS += --sv
EXTRA_ARGS += --timing
EXTRA_ARGS += --assert
EXTRA_ARGS += -Wall
EXTRA_ARGS += -Wno-fatal
EXTRA_ARGS += --coverage
EXTRA_ARGS += -I$(RTL_DIR)

# Pin coverage output to a known path inside SIM_BUILD.
# Without this, coverage.dat lands in the make invocation CWD.
COCOTB_PLUSARGS += +verilator+coverage+file+$(COVERAGE_DAT)

# ---------------------------------------------------------------------------
# Waveforms - opt-in via: make WAVES=1
# ---------------------------------------------------------------------------

ifeq ($(WAVES), 1)
EXTRA_ARGS               += --trace-fst
COCOTB_HDL_TIMEUNIT      ?= 1ns
COCOTB_HDL_TIMEPRECISION ?= 1ps
endif

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

.PHONY: waves coverage-report clean

waves::
	WAVES=1 $(MAKE) sim

# Two-stage report:
#   1. verilator_coverage --write-info -> lcov .info (machine-readable, CI-friendly)
#   2. genhtml -> HTML (human-readable, optional locally)
# Only runs if coverage.dat exists, safe to call after any sim target.
COVERAGE_REPORT_CMD ?= \
    verilator_coverage --write-info $(COVERAGE_INFO) $(COVERAGE_DAT) && \
    echo "Coverage info written to $(COVERAGE_INFO)" && \
    if command -v genhtml >/dev/null 2>&1; then \
        genhtml --output-directory $(COVERAGE_HTML) $(COVERAGE_INFO) && \
        echo "HTML report: $(COVERAGE_HTML)/index.html"; \
    else \
        echo "genhtml not found - skipping HTML report (apt install lcov)"; \
    fi

coverage-report: $(COVERAGE_DAT)
	$(COVERAGE_REPORT_CMD)

clean::
	rm -rf $(SIM_BUILD)
	find . -name '*.vcd'       -delete
	find . -name '*.fst'       -delete
	find . -name '*.fst.hier'  -delete
	find . -name 'results.xml' -delete
