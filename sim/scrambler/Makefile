# sim/scrambler/Makefile
DUT      := scrambler
TOPLEVEL := scrambler
COCOTB_TEST_MODULES := verif.scrambler.test_scrambler

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/scrambler.sv

COMPILE_ARGS += -GDATA_W=8

include $(shell cocotb-config --makefiles)/Makefile.sim
