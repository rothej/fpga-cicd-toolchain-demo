# verif/crc_checker/test_crc_checker.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.crc_checker.env import CrcCheckerEnv
from verif.crc_checker.sequences import CorruptCrcSeq, RandomMixSeq, ValidCrcSeq


class CrcCheckerBaseTest(BaseTest):
    """
    Base test for crc_checker.sv.

    Default: CRC24A (crc_type=0), packets 1-128 bytes, 64 packets.

    drain_cycles=32 covers the two-cycle pipeline latency between the last
    data_valid beat and the crc_pass/crc_fail pulse (crc_engine registers
    crc_out one cycle after last, crc_checker registers crc_ref on the same
    cycle and compares one cycle later).
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        ConfigDB().set(self, "*", "crc_type", 0)  # CRC24A
        ConfigDB().set(self, "*", "min_len", 1)
        ConfigDB().set(self, "*", "max_len", 128)
        ConfigDB().set(self, "*", "count", 64)
        self.env = CrcCheckerEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.init.value = 0
        dut.crc_type.value = 0
        dut.data_in.value = 0
        dut.data_valid.value = 0
        dut.last.value = 0
        dut.crc_ref.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class ValidCrcTest(CrcCheckerBaseTest):
    """64 CRC24A packets - all valid CRCs. Expect crc_pass for every packet."""

    async def body(self) -> None:
        await ValidCrcSeq("valid_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class CorruptCrcTest(CrcCheckerBaseTest):
    """32 CRC24A packets - all single-bit-flipped CRCs. Expect crc_fail for every packet."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "count", 32)
        await CorruptCrcSeq("corrupt_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class RandomMixTest(CrcCheckerBaseTest):
    """64 CRC24A packets - 50/50 valid/corrupt mix. Exercises all four cross cells."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "count", 64)
        ConfigDB().set(self, "*", "corrupt_ratio", 0.5)
        await RandomMixSeq("mix_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc16Test(CrcCheckerBaseTest):
    """
    64 valid CRC16 packets (UCI/PUSCH path).

    crc_type=3 maps to CRC16 (3'b011) in crc_pkg.sv.
    Exercises the 16-bit polynomial path through crc_engine.
    """

    def build_phase(self) -> None:
        super().build_phase()
        ConfigDB().set(self, "*", "crc_type", 3)  # CRC16 = 3'b011

    async def body(self) -> None:
        await ValidCrcSeq("crc16_seq").start(self.env.tx_agent.sequencer)
