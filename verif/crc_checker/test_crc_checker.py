# verif/crc_checker/test_crc_checker.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.crc_checker.env import CrcCheckerEnv
from verif.crc_checker.sequences import CorruptCrcSeq, RandomMixSeq, ValidCrcSeq

_DEFAULT_CRC_TYPE: int = 0  # CRC24A


class CrcCheckerBaseTest(BaseTest):
    """
    Base test for crc_checker.sv.

    drain_cycles=32 covers the two-cycle pipeline latency between the last
    data_valid beat and the crc_pass/crc_fail pulse.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
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
        seq = ValidCrcSeq("valid_seq")
        seq.crc_type = _DEFAULT_CRC_TYPE
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 64
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class CorruptCrcTest(CrcCheckerBaseTest):
    """32 CRC24A packets - all single-bit-flipped CRCs. Expect crc_fail for every packet."""

    async def body(self) -> None:
        seq = CorruptCrcSeq("corrupt_seq")
        seq.crc_type = _DEFAULT_CRC_TYPE
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class RandomMixTest(CrcCheckerBaseTest):
    """64 CRC24A packets - 50/50 valid/corrupt mix. Exercises all four cross cells."""

    async def body(self) -> None:
        seq = RandomMixSeq("mix_seq")
        seq.crc_type = _DEFAULT_CRC_TYPE
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 64
        seq.corrupt_ratio = 0.5
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc16Test(CrcCheckerBaseTest):
    """
    64 valid CRC16 packets (UCI/PUSCH path).

    crc_type=3 maps to CRC16 (3'b011) in crc_pkg.sv.
    Exercises the 16-bit polynomial path through crc_engine.
    """

    async def body(self) -> None:
        seq = ValidCrcSeq("crc16_seq")
        seq.crc_type = 3  # CRC16 = 3'b011
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 64
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc24BTest(CrcCheckerBaseTest):
    """
    32 valid/corrupt CRC24B packets (code-block segmentation path).

    crc_type=1 maps to CRC24B (3'b001) in crc_pkg.sv.
    Exercises get_crc_width/poly/mask case arm 1 for the first time.
    """

    async def body(self) -> None:
        seq = RandomMixSeq("crc24b_seq")
        seq.crc_type = 1  # CRC24B = 3'b001
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 32
        seq.corrupt_ratio = 0.5
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc24CTest(CrcCheckerBaseTest):
    """
    32 valid/corrupt CRC24C packets (UL-SCH, LDPC base graph 1).

    crc_type=2 maps to CRC24C (3'b010) in crc_pkg.sv.
    """

    async def body(self) -> None:
        seq = RandomMixSeq("crc24c_seq")
        seq.crc_type = 2  # CRC24C = 3'b010
        seq.min_len = 1
        seq.max_len = 128
        seq.count = 32
        seq.corrupt_ratio = 0.5
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc11Test(CrcCheckerBaseTest):
    """
    32 valid/corrupt CRC11 packets (UCI on PUCCH formats 2/3/4).

    crc_type=4 maps to CRC11 (3'b100) in crc_pkg.sv.
    Exercises the 11-bit mask path in get_crc_mask for the first time.
    """

    async def body(self) -> None:
        seq = RandomMixSeq("crc11_seq")
        seq.crc_type = 4  # CRC11 = 3'b100
        seq.min_len = 1
        seq.max_len = 32
        seq.count = 32
        seq.corrupt_ratio = 0.5
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class Crc6Test(CrcCheckerBaseTest):
    """
    32 valid/corrupt CRC6 packets (UCI on PUCCH, payload <= 11 bits).

    crc_type=5 maps to CRC6 (3'b101) in crc_pkg.sv.
    Exercises the 6-bit mask path in get_crc_mask for the first time.
    """

    async def body(self) -> None:
        seq = RandomMixSeq("crc6_seq")
        seq.crc_type = 5  # CRC6 = 3'b101
        seq.min_len = 1
        seq.max_len = 4
        seq.count = 32
        seq.corrupt_ratio = 0.5
        await seq.start(self.env.tx_agent.sequencer)
