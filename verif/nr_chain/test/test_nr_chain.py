# verif/nr_chain/test_nr_chain.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.nr_chain.env import NrChainEnv
from verif.nr_chain.sequences import (
    DefaultLoopbackVSeq,
    MultiSymbolBlockVSeq,
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

    ConfigDB: n_fft is set here so the driver, scoreboard and coverage
    collector all use the same value as the compile-time N_FFT.

    drain_cycles=4000:
        NrChainDriver blocks on m_axis_tlast for every block, so every
        block has already left the RX chain when body() returns. The drain
        only gives the monitors and scoreboard time to settle, and 4000
        cycles is deliberately generous. It does not need to scale with
        block count or N_FFT.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        ConfigDB().set(self, "*", "drain_cycles", 4000)
        ConfigDB().set(self, "*", "samp_w", _SAMP_W)
        ConfigDB().set(self, "*", "data_w", _DATA_W)
        ConfigDB().set(self, "*", "n_fft", _N_FFT)
        super().build_phase()
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
    TX cp_inserter and RX cp_remover receive the same cp_len sideband.
    A TX-side bug shows up as a wrong loopback sample count or tuser index;
    an RX-side bug (e.g. wrong discard count) shows up as a payload mismatch.
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
    Isolates scrambler seed-loading (TX cinit_load and the RX tuser-triggered
    reseed) from CP handling, which stays fixed at cp_len=9.
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
class SingleBlockTest(NrChainBaseTest):
    """
    One N_FFT-byte block (one OFDM symbol) after reset.

    N_FFT bytes is the smallest block the chain supports: nr_tx_chain neither
    pads nor carries a length, so payload_len must be a non-zero multiple of
    N_FFT (enforced in NrChainDriver). Targets the first-block-after-reset
    path: TX_CINIT armed by reset, RX cp_len latched from idle.
    """

    async def body(self) -> None:
        vseq = DefaultLoopbackVSeq("single_block_v")
        vseq.payload_len = _N_FFT
        vseq.cp_len = 9
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        vseq.count = 1
        await vseq.start(self.env.vseqr)


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


@pyuvm.test()
class MultiSymbolBlockTest(NrChainBaseTest):
    """
    Three OFDM symbols in one block. Scoreboard asserts 3*(N_FFT+cp_len)
    loopback samples and a single block-start tuser at index cp_len;
    exercises cp_inserter backpressure with TX_IDLE active and the RX
    tuser-based (not gap-based) reseed.
    """

    async def body(self) -> None:
        vseq = MultiSymbolBlockVSeq("multi_symbol_v")
        vseq.n_fft = _N_FFT
        vseq.n_symbols = 3
        vseq.cp_len = 9
        vseq.scrambler_seed = 0x00_0001
        vseq.data_w = _DATA_W
        vseq.mod_order = _MOD_ORDER
        await vseq.start(self.env.vseqr)
