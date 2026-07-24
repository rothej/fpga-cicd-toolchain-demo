# verif/cp_remover/test_cp_remover.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.cp_remover.env import CpRemoverEnv
from verif.cp_remover.sequences import (
    CountingPatternSeq,
    MaxCpLenSeq,
    MultiSymbolSeq,
    VaryingCpLenSeq,
    ZeroCpSeq,
)


class CpRemoverBaseTest(BaseTest):
    """
    Base test for cp_remover.sv.

    Compile-time parameters (set via Makefile):
        N_FFT      = 64 - OFDM symbol length in samples (output packet length)
        CP_LEN_MAX = 16 - maximum cyclic prefix length
        SAMP_W     = 16 - sample word width in bits

    drain_cycles=32 covers the shallow combinational output pipeline of
    cp_remover.sv - at most a handful of register stages after the last
    accepted input beat.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        ConfigDB().set(self, "*", "n_fft", 64)
        ConfigDB().set(self, "*", "cp_len", 9)
        ConfigDB().set(self, "*", "samp_w", 16)
        ConfigDB().set(self, "*", "count", 16)
        self.env = CpRemoverEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class DefaultCpTest(CpRemoverBaseTest):
    """
    16 random packets, N_FFT=64, cp_len=9.
    Smoke test for standard CP removal at ~14% overhead.
    """

    async def body(self) -> None:
        await MultiSymbolSeq("default_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class ZeroCpTest(CpRemoverBaseTest):
    """
    8 packets with cp_len=0 - pure passthrough.
    Output must equal input verbatim; tlast must fire at beat N_FFT-1.
    """

    async def body(self) -> None:
        await ZeroCpSeq("zero_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class CountingPatternTest(CpRemoverBaseTest):
    """
    Deterministic counting packet: full_samples[i] = i.
    First output beat must equal cp_len (not 0) - easily verifiable
    on a waveform viewer without any scoreboard decode.
    """

    async def body(self) -> None:
        await CountingPatternSeq("counting_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class VaryingCpLenTest(CpRemoverBaseTest):
    """
    Five back-to-back packets with cp_len in [0, 4, 8, 12, 16].
    Exercises runtime cp_len reconfiguration between consecutive packets.
    Mirrors the 5G NR slot structure on the receiver side.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "cp_lens", [0, 4, 8, 12, 16])
        await VaryingCpLenSeq("varying_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MultiSymbolBackToBackTest(CpRemoverBaseTest):
    """
    32 back-to-back packets at cp_len=9.
    Regression for inter-symbol contamination: payload samples from packet N
    must not appear in the output of packet N+1.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "count", 32)
        await MultiSymbolSeq("multi_bt_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MaxCpLenTest(CpRemoverBaseTest):
    """
    Single packet with cp_len=CP_LEN_MAX (16).
    Stresses the discard counter at its maximum depth.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "cp_len", 16)
        await MaxCpLenSeq("max_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class SingleSampleCpTest(CpRemoverBaseTest):
    """
    16 packets with cp_len=1.
    Fence-post stress: the discard counter must suppress exactly one beat
    and assert m_axis_tvalid on the very next beat.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "cp_len", 1)
        ConfigDB().set(self, "*", "count", 16)
        await MultiSymbolSeq("single_samp_seq").start(self.env.tx_agent.sequencer)
