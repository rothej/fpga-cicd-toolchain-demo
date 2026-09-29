# sim/qam_mapper/Makefile
DUT      := qam_mapper
TOPLEVEL := qam_mapper
COCOTB_TEST_MODULES := verif.qam_mapper.test.test_qam_mapper

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/qam_mapper.sv

# DATA_W=8: accepts up to 8 bits per transfer (256-QAM max; mod_order runtime)
# IQ_W=8:   signed 8-bit I and Q output (range covers +/-15 for 256-QAM)
COMPILE_ARGS += -GDATA_W=8 -GIQ_W=8

include $(shell cocotb-config --makefiles)/Makefile.sim
