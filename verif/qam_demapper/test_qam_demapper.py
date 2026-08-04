# verif/qam_demapper/test_qam_demapper.py

from __future__ import annotations

import cocotb
import pyuvm
from pyuvm import ConfigDB

from verif.common.base_test import BaseTest
from verif.qam_demapper.env import QamDemapperEnv
from verif.qam_demapper.sequences import (
    AllConstellationPointsSeq,
    AllModOrdersRoundtripSeq,
    RoundtripSeq,
)

_IQ_W: int = 8
_DATA_W: int = 8


class QamDemapperBaseTest(BaseTest):
    """
    Base test for qam_demapper.sv.

    IQ_W=8: input tdata = {I[7:0], Q[7:0]} - 16-bit bus, I in upper half.
    DATA_W=8: output tdata carries mod_order LSBs of the recovered word.
    drain_cycles=32 covers the one-cycle registered output latency.
    """

    def build_phase(self) -> None:
        ConfigDB().set(None, "*", "dut", cocotb.top)
        super().build_phase()
        ConfigDB().set(self, "*", "drain_cycles", 32)
        # iq_w consumed by QamDemapperDriver (a component).
        ConfigDB().set(self, "*", "iq_w", _IQ_W)
        # data_w consumed by QamDemapperOutputMonitor (a component).
        ConfigDB().set(self, "*", "data_w", _DATA_W)
        self.env = QamDemapperEnv.create("env", self)

    async def pre_body(self) -> None:
        dut = self.dut
        dut.mod_order.value = 2
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0

    async def body(self) -> None:  # pragma: no cover
        raise NotImplementedError


@pyuvm.test()
class QpskRoundtripTest(QamDemapperBaseTest):
    """32 random QPSK packets. Verifies +/-90 -> bit recovery at all four points."""

    async def body(self) -> None:
        seq = RoundtripSeq("qpsk_rt_seq")
        seq.mod_order = 2
        seq.iq_w = _IQ_W
        seq.min_len = 8
        seq.max_len = 256
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class SixteenQamRoundtripTest(QamDemapperBaseTest):
    """32 random 16-QAM packets. Verifies +/-24, +/-72 level recovery."""

    async def body(self) -> None:
        seq = RoundtripSeq("16qam_rt_seq")
        seq.mod_order = 4
        seq.iq_w = _IQ_W
        seq.min_len = 8
        seq.max_len = 256
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class SixtyFourQamRoundtripTest(QamDemapperBaseTest):
    """32 random 64-QAM packets. Verifies +/-12 through +/-84 level recovery."""

    async def body(self) -> None:
        seq = RoundtripSeq("64qam_rt_seq")
        seq.mod_order = 6
        seq.iq_w = _IQ_W
        seq.min_len = 8
        seq.max_len = 256
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class TwoFiftySixQamRoundtripTest(QamDemapperBaseTest):
    """32 random 256-QAM packets. Full 15-level-per-component recovery."""

    async def body(self) -> None:
        seq = RoundtripSeq("256qam_rt_seq")
        seq.mod_order = 8
        seq.iq_w = _IQ_W
        seq.min_len = 8
        seq.max_len = 256
        seq.count = 32
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllModOrdersRoundtripTest(QamDemapperBaseTest):
    """
    One roundtrip packet each: QPSK -> 16-QAM -> 64-QAM -> 256-QAM.
    Verifies correct DUT reconfiguration when mod_order changes between packets.
    """

    async def body(self) -> None:
        seq = AllModOrdersRoundtripSeq("all_mo_rt_seq")
        seq.iq_w = _IQ_W
        seq.min_len = 16
        seq.max_len = 128
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllQpskConstellationPointsTest(QamDemapperBaseTest):
    """
    All 4 QPSK constellation points in one packet.
    Guarantees 100% input constellation and output word coverage for QPSK.
    """

    async def body(self) -> None:
        seq = AllConstellationPointsSeq("qpsk_pts_seq")
        seq.mod_order = 2
        seq.iq_w = _IQ_W
        await seq.start(self.env.tx_agent.sequencer)


@pyuvm.test()
class AllSixteenQamConstellationPointsTest(QamDemapperBaseTest):
    """
    All 16 constellation points of 16-QAM in a single packet.
    Directly validates the full 4-bit Gray-coded recovery table.
    """

    async def body(self) -> None:
        seq = AllConstellationPointsSeq("16qam_pts_seq")
        seq.mod_order = 4
        seq.iq_w = _IQ_W
        await seq.start(self.env.tx_agent.sequencer)
