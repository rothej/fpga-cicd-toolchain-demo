# sim/crc_engine/Makefile
#
# Verilator + cocotb/pyuvm simulation for crc_engine.sv
#
# Invocation examples:
#   make                                 - run all three test cases
#   COCOTB_TESTCASE=TestCrcRandom make   - run a single test case
#                                          (native cocotb env var -
#                                           no custom target needed)
#   make WAVES=1                         - random test + FST waveform
#   make CRC_WIDTH=16 POLY=0x11021       - CRC16 parameter override
#   make coverage-report                 - merge + annotate coverage dbs
#   make clean                           - remove sim_build/, logs, waveforms

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

DUT      := crc_engine
TOPLEVEL := crc_engine
COCOTB_TEST_MODULES := verif.crc_engine.test.test_crc_engine

include ../common.mk

# ---------------------------------------------------------------------------
# RTL sources
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

include $(shell cocotb-config --makefiles)/Makefile.sim
