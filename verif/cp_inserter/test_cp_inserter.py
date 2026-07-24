# verif/cp_inserter/test_cp_inserter.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.cp_inserter.env import CpInserterEnv
from verif.cp_inserter.sequences import (
    CountingPatternSeq,
    MultiSymbolSeq,
    RandomSingleSymbolSeq,
    VaryingCpLenSeq,
    ZeroCpSeq,
)


class CpInserterBaseTest(BaseTest):
    """
    Base test for cp_inserter.sv.

    Compile-time parameters (set via Makefile):
        N_FFT      = 64 - OFDM symbol length in samples
        CP_LEN_MAX = 16 - maximum cyclic prefix length; cp_len <= 16 always
        SAMP_W     = 16 - sample word width in bits

    drain_cycles=128 covers the N_FFT=64 buffer-fill latency plus margin for
    the final EMIT_SYM phase to complete after the last input beat.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 128)
        ConfigDB().set(self, "*", "n_fft", 64)
        ConfigDB().set(self, "*", "cp_len", 9)
        ConfigDB().set(self, "*", "samp_w", 16)
        ConfigDB().set(self, "*", "count", 16)
        self.env = CpInserterEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class DefaultCpTest(CpInserterBaseTest):
    """
    16 random symbols, N_FFT=64, cp_len=9.
    Smoke test for standard CP insertion at ~14% overhead.
    """

    async def body(self) -> None:
        await MultiSymbolSeq("default_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class ZeroCpTest(CpInserterBaseTest):
    """
    8 symbols with cp_len=0 - pure passthrough.
    Output must equal input verbatim; DUT must assert tlast at beat N_FFT-1.
    """

    async def body(self) -> None:
        await ZeroCpSeq("zero_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class CountingPatternTest(CpInserterBaseTest):
    """
    Deterministic counting symbol: samples[i] = i.
    CP copy is unambiguous in the waveform viewer without any decode step.
    """

    async def body(self) -> None:
        await CountingPatternSeq("counting_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class VaryingCpLenTest(CpInserterBaseTest):
    """
    Five back-to-back symbols with cp_len in [0, 4, 8, 12, 16].
    Exercises runtime cp_len reconfiguration between consecutive symbols.
    Mirrors the 5G NR slot structure: symbol 0 carries the extended CP.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "cp_lens", [0, 4, 8, 12, 16])
        await VaryingCpLenSeq("varying_cp_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MultiSymbolBackToBackTest(CpInserterBaseTest):
    """
    32 back-to-back symbols at cp_len=9.
    Regression for inter-symbol contamination: samples from symbol N must
    not bleed into the CP or payload of symbol N+1.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "count", 32)
        await MultiSymbolSeq("multi_bt_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MaxCpLenTest(CpInserterBaseTest):
    """
    Single symbol with cp_len=CP_LEN_MAX (16).
    Stresses the DUT's internal buffer at full depth.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "cp_len", 16)
        await RandomSingleSymbolSeq("max_cp_seq").start(self.env.tx_agent.sequencer)
