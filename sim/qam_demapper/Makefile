# sim/qam_demapper/Makefile
DUT      := qam_demapper
TOPLEVEL := qam_demapper
COCOTB_TEST_MODULES := verif.qam_demapper.test.test_qam_demapper

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/qam_demapper.sv


# IQ_W=8:   signed 8-bit I and Q input (covers +/-15 for 256-QAM)
# DATA_W=8: recovered output word width (256-QAM uses all 8 bits)
COMPILE_ARGS += -GIQ_W=8 -GDATA_W=8

include $(shell cocotb-config --makefiles)/Makefile.sim
