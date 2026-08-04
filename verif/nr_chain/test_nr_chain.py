# verif/nr_chain/test_nr_chain.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.nr_chain.env import NrChainEnv
from verif.nr_chain.sequences import (
    DefaultLoopbackVSeq,
    MinPayloadLoopbackSeq,
    SeedSweepVSeq,
    StressVSeq,
    VaryingCpVSeq,
)

_N_FFT: int = 64
_CP_LEN_MAX: int = 16
_SAMP_W: int = 16
_DATA_W: int = 8
_MOD_ORDER: int = 2  # must match Makefile -GMOD_ORDER; controls payload bit width


class NrChainBaseTest(BaseTest):
    """
    Base test for nr_chain loopback (nr_tx_chain -> nr_rx_chain).

    Compile-time parameters (set via Makefile):
        N_FFT      = 64  - OFDM symbol length in samples
        CP_LEN_MAX = 16  - maximum cyclic prefix length
        SAMP_W     = 16  - sample word width at TX/RX boundary
        MOD_ORDER  = 2   - bits per QAM symbol (2=QPSK)
        DATA_W     = 8   - data bus width in bits
        POLY_W     = 24  - CRC polynomial width (3-byte CRC-24A)

    drain_cycles=4000:
        Covers the full TX+RX pipeline for up to 32 back-to-back blocks at
        N_FFT=64 / QPSK. Recalculate if N_FFT or count is increased:
            drain ≈ count × ceil((payload_len + POLY_W/8) × 8
                                 / (N_FFT × MOD_ORDER))
                          × (N_FFT + CP_LEN_MAX) × 2
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        # drain_cycles MUST be set before super().build_phase() because
        # BaseTest.build_phase() reads it via _cfg(). Setting it afterward
        # has no effect — the field is already assigned to the default (0).
        ConfigDB().set(self, "*", "drain_cycles", 4000)
        super().build_phase()
        # samp_w consumed by NrChainLoopbackMonitor (a component).
        ConfigDB().set(self, "*", "samp_w", _SAMP_W)
        # data_w consumed by NrChainDriver and NrChainOutputMonitor (components).
        ConfigDB().set(self, "*", "data_w", _DATA_W)
        self.env = NrChainEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0
        dut.scrambler_seed.value = 0
        dut.m_axis_tready.value = 1

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class DefaultLoopbackTest(NrChainBaseTest):
    """
    16 random transport blocks, N_FFT=64, cp_len=9, QPSK, seed=0x000001.
    Smoke test for the full TX->RX pipeline under standard NR parameters.
    """

    async def body(self) -> None:
        vseq = DefaultLoopbackVSeq("default_v")
        vseq.payload_len = 64
        vseq.cp_len = 9
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.count = 16
        await vseq.start(self.env.vseqr)


@pyuvm.test()
class VaryingCpTest(NrChainBaseTest):
    """
    Five blocks with cp_len in [0, 4, 8, 12, 16].
    TX cp_inserter and RX cp_remover receive the same cp_len sideband -
    any mismatch between the two produces a CRC failure, not a length error.
    """

    async def body(self) -> None:
        vseq = VaryingCpVSeq("varying_cp_v")
        vseq.payload_len = 64
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.cp_lens = [0, 4, 8, 12, 16]
        await vseq.start(self.env.vseqr)


@pyuvm.test()
class SeedSweepTest(NrChainBaseTest):
    """
    Four scrambler seeds, identical 64-byte payload each time.
    All four recovered payloads must equal the original.
    Isolates scrambler seed-loading from CRC and QAM logic.
    """

    async def body(self) -> None:
        vseq = SeedSweepVSeq("seed_sweep_v")
        vseq.payload_len = 64
        vseq.cp_len = 9
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.scrambler_seeds = [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF]
        await vseq.start(self.env.vseqr)


@pyuvm.test()
class MinPayloadTest(NrChainBaseTest):
    """
    Single one-byte transport block.
    Stresses the minimum-length path through every stage of both chains.
    """

    async def body(self) -> None:
        seq = MinPayloadLoopbackSeq("min_payload")
        seq.cp_len = 9
        seq.scrambler_seed = 0x00_0001
        seq.data_w = _DATA_W
        seq.mod_order = _MOD_ORDER
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MultiBlockBackToBackTest(NrChainBaseTest):
    """
    32 back-to-back transport blocks at cp_len=9, seed=0x000001.
    Primary regression for inter-block contamination.
    """

    async def body(self) -> None:
        vseq = DefaultLoopbackVSeq("multi_bt_v")
        vseq.payload_len = 64
        vseq.cp_len = 9
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.count = 32
        await vseq.start(self.env.vseqr)


@pyuvm.test()
class StressTest(NrChainBaseTest):
    """
    Three-phase stress: seed sweep -> varying CP -> 32 back-to-back blocks.
    Exercises all runtime parameter combinations in a single run.
    """

    async def body(self) -> None:
        vseq = StressVSeq("stress_v")
        vseq.payload_len = 64
        vseq.cp_len = 9
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.scrambler_seeds = [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF]
        vseq.cp_lens = [0, 4, 8, 12, 16]
        vseq.multi_count = 32
        await vseq.start(self.env.vseqr)


@pyuvm.test()
class ZeroCpLoopbackTest(NrChainBaseTest):
    """
    16 blocks with cp_len=0 end-to-end.
    TX chain inserts no CP prefix; RX chain must strip zero samples.
    """

    async def body(self) -> None:
        vseq = DefaultLoopbackVSeq("zero_cp_v")
        vseq.payload_len = 64
        vseq.cp_len = 0
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.count = 16
        await vseq.start(self.env.vseqr)
