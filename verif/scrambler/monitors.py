# verif/scrambler/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component


class ScramblerOutputItem:
    """One complete scrambled packet sampled from m_axis_*."""

    def __init__(self, data: list[int]) -> None:
        self.data = data

    def __repr__(self) -> str:
        return f"ScramblerOutputItem(len={len(self.data)})"


class ScramblerOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on scrambler.sv's m_axis_* output.

    Holds m_axis_tready=1 continuously (no backpressure).
    Publishes one ScramblerOutputItem per packet (terminated by tlast=1).
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")

    async def run_phase(self) -> None:
        dut = self.dut
        dut.m_axis_tready.value = 1  # always ready

        while True:
            packet: list[int] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    packet.append(int(dut.m_axis_tdata.value))
                    if dut.m_axis_tlast.value:
                        break
            self.ap.write(ScramblerOutputItem(packet))
