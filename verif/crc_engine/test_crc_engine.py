# verif/crc_engine/test_crc_engine.py

"""
verif/crc_engine/test_crc_engine.py

Concrete test classes for the crc_engine testbench.

Follows the same BaseTest pattern as all other unit TBs.
The sim/crc_engine/Makefile's run-* sub-targets select individual
tests via COCOTB_TESTCASE=<ClassName>.
"""

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.common.nr_ref_model import CrcPoly
from verif.crc_engine.env import CrcEngineEnv
from verif.crc_engine.sequences import (
    CrcEdgeCaseSeq,
    CrcKnownVectorSeq,
    CrcRandomSeq,
)

_CRC_POLY = CrcPoly.CRC24A
_CRC_WIDTH = 24


class CrcEngineBaseTest(BaseTest):
    """
    Base test for crc_engine.sv.

    drain_cycles=32 covers the one-cycle pipeline latency between the
    final data_valid && last beat and the crc_valid pulse.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        ConfigDB().set(self, "*", "crc_poly", _CRC_POLY)
        ConfigDB().set(self, "*", "crc_width", _CRC_WIDTH)
        self.env = CrcEngineEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.init.value = 0
        dut.crc_type.value = 0
        dut.data_in.value = 0
        dut.data_valid.value = 0
        dut.last.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class TestCrcKnownVectors(CrcEngineBaseTest):
    """
    Drive _KNOWN_PAYLOADS and check DUT output against crc_compute().

    Because the scoreboard derives expected values from the reference model
    at run time, this test simultaneously validates both the reference model
    and the DUT for every payload in the fixed set.
    """

    async def body(self) -> None:
        await CrcKnownVectorSeq("known_vec_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class TestCrcRandom(CrcEngineBaseTest):
    """
    64 random payloads, seeded for reproducibility.

    Seed 0xC0DE is arbitrary. Override via ConfigDB to sweep seeds in CI.
    """

    def build_phase(self) -> None:
        super().build_phase()
        ConfigDB().set(self, "*", "rand_count", 64)
        ConfigDB().set(self, "*", "rand_min_len", 1)
        ConfigDB().set(self, "*", "rand_max_len", 128)
        ConfigDB().set(self, "*", "rand_seed", 0xC0DE)

    async def body(self) -> None:
        await CrcRandomSeq("random_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class TestCrcEdgeCases(CrcEngineBaseTest):
    """
    Single-byte and 255-byte payloads.
    Stresses LFSR boundary conditions at both ends of the length range.
    """

    async def body(self) -> None:
        await CrcEdgeCaseSeq("edge_seq").start(self.env.tx_agent.sequencer)
