# verif/scrambler/test_scrambler.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.scrambler.env import ScramblerEnv
from verif.scrambler.sequences import AllZerosSeq, MultiCinitSeq, RandomDataSeq

_DATA_W: int = 8


class ScramblerBaseTest(BaseTest):
    """
    Base test for scrambler.sv.

    drain_cycles=32 covers the one-cycle registered output latency plus
    margin for the monitor to observe the final tlast beat.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        self.env = ScramblerEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.cinit_load.value = 0
        dut.cinit.value = 0
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class RandomDataTest(ScramblerBaseTest):
    """32 random-data packets, fixed cinit. Baseline scrambler check."""

    async def body(self) -> None:
        seq = RandomDataSeq("rand_seq")
        seq.cinit = 0x12345678 & 0x7FFFFFFF
        seq.data_w = _DATA_W
        seq.min_len = 8
        seq.max_len = 256
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllZerosTest(ScramblerBaseTest):
    """
    All-zero input - output must equal the Gold sequence exactly.
    Directly validates LFSR initialisation and output XOR logic.
    """

    async def body(self) -> None:
        seq = AllZerosSeq("zeros_seq")
        seq.cinit = 0x12345678 & 0x7FFFFFFF
        seq.data_w = _DATA_W
        seq.length = 256
        seq.count = 4
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class MultiCinitTest(ScramblerBaseTest):
    """
    One packet per entry in _TEST_CINIT_VALUES.
    Verifies Gold-sequence re-initialisation between bursts.
    """

    async def body(self) -> None:
        seq = MultiCinitSeq("multi_cinit_seq")
        seq.data_w = _DATA_W
        seq.min_len = 16
        seq.max_len = 128
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class LongPacketTest(ScramblerBaseTest):
    """
    Single 8192-word packet.
    Stresses LFSR state continuity - no wrap-around or reset mid-burst.
    """

    async def body(self) -> None:
        seq = RandomDataSeq("long_seq")
        seq.cinit = 0x12345678 & 0x7FFFFFFF
        seq.data_w = _DATA_W
        seq.min_len = 8192
        seq.max_len = 8192
        seq.count = 1
        await seq.start(self.env.tx_agent.sequencer)
