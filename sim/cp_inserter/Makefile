# sim/cp_inserter/Makefile
DUT      := cp_inserter
TOPLEVEL := cp_inserter
COCOTB_TEST_MODULES := verif.cp_inserter.test_cp_inserter

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/cp_inserter.sv

# N_FFT=64:      OFDM symbol length in samples
# CP_LEN_MAX=16: maximum cyclic prefix length; must satisfy CP_LEN_MAX < N_FFT
# SAMP_W=16:     sample word width in bits
COMPILE_ARGS += -GN_FFT=64 -GCP_LEN_MAX=16 -GSAMP_W=16

include $(shell cocotb-config --makefiles)/Makefile.sim
