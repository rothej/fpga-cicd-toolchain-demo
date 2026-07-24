# sim/nr_chain/Makefile
DUT      := nr_chain_top
TOPLEVEL := nr_chain_top
COCOTB_TEST_MODULES := verif.nr_chain.test_nr_chain

include ../common.mk

THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

RTL_SOURCES := \
    $(RTL_DIR)/crc_pkg.sv     \
    $(RTL_DIR)/crc_engine.sv  \
    $(RTL_DIR)/crc_checker.sv \
    $(RTL_DIR)/scrambler.sv   \
    $(RTL_DIR)/qam_mapper.sv  \
    $(RTL_DIR)/qam_demapper.sv \
    $(RTL_DIR)/cp_inserter.sv \
    $(RTL_DIR)/cp_remover.sv  \
    $(RTL_DIR)/nr_tx_chain.sv \
    $(RTL_DIR)/nr_rx_chain.sv

VERILOG_SOURCES := $(RTL_SOURCES)

# N_FFT=64:      OFDM symbol length in samples
# CP_LEN_MAX=16: maximum CP length; CP_LEN_MAX < N_FFT must hold
# SAMP_W=16:     sample word width at the TX->RX loopback boundary
# MOD_ORDER=2:   2=QPSK  (run separate Makefile targets for 4=16QAM, 6=64QAM)
# DATA_W=8:      data bus byte width
# POLY_W=24:     CRC-24A polynomial width (3 CRC bytes appended by TX chain)
COMPILE_ARGS += \
    -GN_FFT=64      \
    -GCP_LEN_MAX=16 \
    -GSAMP_W=16     \
    -GMOD_ORDER=2   \
    -GDATA_W=8      \
    -GPOLY_W=24

include $(shell cocotb-config --makefiles)/Makefile.sim
