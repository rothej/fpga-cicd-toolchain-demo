# sim/cp_remover/Makefile
DUT      := cp_remover
TOPLEVEL := cp_remover
COCOTB_TEST_MODULES := verif.cp_remover.test_cp_remover

include ../common.mk

VERILOG_SOURCES := \
    $(RTL_DIR)/cp_remover.sv

# N_FFT=64:      OFDM symbol length in samples (output packet length)
# CP_LEN_MAX=16: maximum cyclic prefix length; must satisfy CP_LEN_MAX < N_FFT
# SAMP_W=16:     sample word width in bits
COMPILE_ARGS += -GN_FFT=64 -GCP_LEN_MAX=16 -GSAMP_W=16

include $(shell cocotb-config --makefiles)/Makefile.sim
