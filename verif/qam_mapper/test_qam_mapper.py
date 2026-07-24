# verif/qam_mapper/test_qam_mapper.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.qam_mapper.env import QamMapperEnv
from verif.qam_mapper.sequences import (
    AllConstellationPointsSeq,
    AllModOrdersSeq,
    RandomDataSeq,
)


class QamMapperBaseTest(BaseTest):
    """
    Base test for qam_mapper.sv.

    Default IQ layout: m_axis_tdata = {I[IQ_W-1:0], Q[IQ_W-1:0]} (16-bit).
    drain_cycles=32 covers the one-cycle registered output latency.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        ConfigDB().set(self, "*", "data_w", 8)
        ConfigDB().set(self, "*", "iq_w", 8)
        ConfigDB().set(self, "*", "mod_order", 2)  # QPSK default
        ConfigDB().set(self, "*", "min_len", 8)
        ConfigDB().set(self, "*", "max_len", 256)
        ConfigDB().set(self, "*", "count", 32)
        self.env = QamMapperEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.mod_order.value = 2
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class QpskTest(QamMapperBaseTest):
    """32 random QPSK packets. Baseline: all four +/-90 constellation points."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 2)
        await RandomDataSeq("qpsk_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class SixteenQamTest(QamMapperBaseTest):
    """32 random 16-QAM packets. Exercises +/-24, +/-72 levels."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 4)
        await RandomDataSeq("16qam_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class SixtyFourQamTest(QamMapperBaseTest):
    """32 random 64-QAM packets. Exercises +/-12, +/-36, +/-60, +/-84 levels."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 6)
        await RandomDataSeq("64qam_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class TwoFiftySixQamTest(QamMapperBaseTest):
    """32 random 256-QAM packets. Full 8-bit input range exercised."""

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 8)
        await RandomDataSeq("256qam_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllModOrdersTest(QamMapperBaseTest):
    """
    One packet each: QPSK -> 16-QAM -> 64-QAM -> 256-QAM.
    Verifies correct DUT reconfiguration when mod_order changes between packets.
    """

    async def body(self) -> None:
        await AllModOrdersSeq("all_mo_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllQpskConstellationPointsTest(QamMapperBaseTest):
    """
    All 4 QPSK constellation points in one packet.
    Minimal smoke test: fails immediately if any +/-90 mapping is wrong.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 2)
        await AllConstellationPointsSeq("qpsk_pts_seq").start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllSixteenQamConstellationPointsTest(QamMapperBaseTest):
    """
    All 16 constellation points of 16-QAM in a single packet.
    Directly validates the full Gray-coded symbol table - no statistical gaps.
    """

    async def body(self) -> None:
        ConfigDB().set(self, "*", "mod_order", 4)
        await AllConstellationPointsSeq("16qam_pts_seq").start(self.env.tx_agent.sequencer)
