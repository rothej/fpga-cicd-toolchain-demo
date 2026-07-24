# sim/crc_engine/Makefile
#
# Verilator + cocotb/pyuvm simulation for crc_engine.sv
#
# Invocation examples:
#   make                                      - run all three test cases
#   make run-known-vectors                    - known-vector test only
#   make run-random                           - random test only (seed 0xC0DE)
#   make run-edge-cases                       - edge-case test only
#   make run-random WAVES=1                   - random test + FST waveform
#   make run-random CRC_WIDTH=16 POLY=0x11021 - CRC16 parameter override
#   make coverage-report                      - merge + annotate coverage dbs
#   make clean                                - remove sim_build/, logs, waveforms

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

DUT      := crc_engine
TOPLEVEL := crc_engine
COCOTB_TEST_MODULES := verif.crc_engine.test_crc_engine

# ---------------------------------------------------------------------------
# Coverage merge setup
#
# Must sit above include ../common.mk so that:
#   COVERAGE_DAT     overrides common.mk's default single-file path
#   COVERAGE_REPORT_CMD beats the ?= guard in common.mk
# The merge itself is a proper Make target ($(_MERGED_DAT)) defined below,
# so Make's prerequisite chain handles missing-file errors automatically.
# ---------------------------------------------------------------------------

_BASE_BUILD := $(CURDIR)/sim_build

_COV_DATS := \
    $(_BASE_BUILD)/known_vectors/coverage.dat \
    $(_BASE_BUILD)/random/coverage.dat \
    $(_BASE_BUILD)/edge_cases/coverage.dat

_MERGED_DAT := $(_BASE_BUILD)/coverage_merged.dat

# common.mk's coverage-report target depends on $(COVERAGE_DAT); point it at
# the merged file so Make tracks the real prerequisite chain.
COVERAGE_DAT := $(_MERGED_DAT)

# Only report here — the merge step is handled by the $(_MERGED_DAT) target.
# $(COVERAGE_INFO) and $(COVERAGE_HTML) expand at recipe time, after common.mk
# defines them, because this uses = not :=.
COVERAGE_REPORT_CMD = \
    verilator_coverage --write-info $(COVERAGE_INFO) $(COVERAGE_DAT) && \
    echo "Coverage info written to $(COVERAGE_INFO)" && \
    if command -v genhtml >/dev/null 2>&1; then \
        genhtml --output-directory $(COVERAGE_HTML) $(COVERAGE_INFO) && \
        echo "HTML report: $(COVERAGE_HTML)/index.html"; \
    else \
        echo "genhtml not found - skipping HTML report (apt install lcov)"; \
    fi

# ---------------------------------------------------------------------------
# Shared infrastructure
# (defines SIM, VERILATOR_ROOT, PATH, PYTHONPATH, EXTRA_ARGS, WAVES ...)
# ---------------------------------------------------------------------------

include ../common.mk

# ---------------------------------------------------------------------------
# RTL sources
# Order matters: crc_pkg.sv defines the package imported by crc_engine.sv.
# Verilator elaborates packages in source order.
# ---------------------------------------------------------------------------

VERILOG_SOURCES := \
    $(RTL_DIR)/crc_pkg.sv \
    $(RTL_DIR)/crc_engine.sv

# ---------------------------------------------------------------------------
# DUT-level parameter overrides
#
# CRC_WIDTH and POLY correspond to the #(parameter ...) declarations in
# crc_engine.sv. Verilator's -G flag requires Verilog integer literal
# syntax (N'hXXXXXX); the shell call converts a plain C-style hex number
# to that form so make variables stay readable.
#
# Default: CRC24A - 24-bit, polynomial 0x864CFB (TS 38.212 S5.1)
# ---------------------------------------------------------------------------

CRC_WIDTH ?= 24
POLY      ?= 0x864CFB

COMPILE_ARGS += -GCRC_WIDTH=$(CRC_WIDTH)
COMPILE_ARGS += "-GPOLY=$(CRC_WIDTH)'h$(shell printf '%X' $(POLY))"

# ---------------------------------------------------------------------------
# Per-testcase sub-make targets
#
# Each target re-invokes make with:
#   COCOTB_TESTCASE - selects exactly one @cocotb.test() entry point
#   SIM_BUILD       - isolates Verilator object cache and coverage.dat so
#                     parallel CI matrix jobs cannot corrupt each other
#
# The sub-make resolves to cocotb's 'sim' goal (from Makefile.sim below),
# not this file's all-tests dispatcher.
# ---------------------------------------------------------------------------

_BASE_BUILD := $(CURDIR)/sim_build

.PHONY: run-known-vectors run-random run-edge-cases

run-known-vectors:
	$(MAKE) COCOTB_TESTCASE=TestCrcKnownVectors \
	        SIM_BUILD=$(_BASE_BUILD)/known_vectors

run-random:
	$(MAKE) COCOTB_TESTCASE=TestCrcRandom \
	        SIM_BUILD=$(_BASE_BUILD)/random

run-edge-cases:
	$(MAKE) COCOTB_TESTCASE=TestCrcEdgeCases \
	        SIM_BUILD=$(_BASE_BUILD)/edge_cases

# ---------------------------------------------------------------------------
# Default goal
#
# Guard on COCOTB_TESTCASE: when set this is a sub-make invoked by a run-*
# target. In that case all-tests must not be the default - cocotb's 'sim'
# goal (included below) takes over, preventing infinite recursion.
# ---------------------------------------------------------------------------

ifeq ($(COCOTB_TESTCASE),)
  .DEFAULT_GOAL := all-tests

  .PHONY: all-tests
  all-tests: run-known-vectors run-random run-edge-cases
else
	# Sub-make invoked by a run-* target. Delegate directly to cocotb's sim rule.
	.DEFAULT_GOAL := sim
endif

# ---------------------------------------------------------------------------
# Coverage merge target
#
# Declared after include ../common.mk so SIM_BUILD and PATH are resolved.
# Make's prerequisite check replaces the old manual shell validation loop:
# if any of the three coverage.dat files is absent, Make errors here with
# a clear "No rule to make target" message naming the missing file.
# ---------------------------------------------------------------------------

$(_MERGED_DAT): $(_COV_DATS)
	@echo "Merging coverage databases..."
	verilator_coverage --write $@ $^

# ---------------------------------------------------------------------------
# Delegate to cocotb's Makefile.sim for compile + sim rules.
# Must be the last include - all variables must be fully set above.
# ---------------------------------------------------------------------------

include $(shell cocotb-config --makefiles)/Makefile.sim
