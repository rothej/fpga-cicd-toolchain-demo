# verif/qam_demapper/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from verif.common.config_utils import _cfg


class QamDemapperOutputItem:
    """One complete demapped packet: a list of recovered data words."""

    def __init__(self, words: list[int]) -> None:
        self.words = words

    def __repr__(self) -> str:
        return f"QamDemapperOutputItem(n_words={len(self.words)})"


class QamDemapperOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on qam_demapper.sv's m_axis_* output.

    Holds m_axis_tready=1 continuously - no output backpressure.
    Collects DATA_W-bit words per beat; publishes one QamDemapperOutputItem
    per tlast-terminated packet.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.data_w = _cfg(self, "data_w", 8)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.m_axis_tready.value = 1
        mask = (1 << self.data_w) - 1

        while True:
            words: list[int] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    words.append(int(dut.m_axis_tdata.value) & mask)
                    if dut.m_axis_tlast.value:
                        break
            self.ap.write(QamDemapperOutputItem(words))
