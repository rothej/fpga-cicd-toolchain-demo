# sim/crc_checker/Makefile
DUT      := crc_checker
TOPLEVEL := crc_checker
COCOTB_TEST_MODULES := verif.crc_checker.test.test_crc_checker

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/crc_pkg.sv    \
    $(RTL_DIR)/crc_engine.sv \
    $(RTL_DIR)/crc_checker.sv

include $(shell cocotb-config --makefiles)/Makefile.sim
