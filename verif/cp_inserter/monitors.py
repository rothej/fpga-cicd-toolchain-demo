# verif/cp_inserter/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from verif.common.config_utils import _cfg


class CpInserterOutputItem:
    """One complete CP-inserted symbol: cp_len + N_FFT sample words."""

    def __init__(self, samples: list[int]) -> None:
        self.samples = samples

    def __repr__(self) -> str:
        return f"CpInserterOutputItem(n_samples={len(self.samples)})"


class CpInserterOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on cp_inserter.sv's m_axis_* output.

    Holds m_axis_tready=1 continuously - no output backpressure modelled.
    Collects SAMP_W-bit words per accepted beat; publishes one
    CpInserterOutputItem per tlast-terminated packet.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.samp_w = _cfg(self, "samp_w", 16)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.m_axis_tready.value = 1
        mask = (1 << self.samp_w) - 1

        while True:
            samples: list[int] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    samples.append(int(dut.m_axis_tdata.value) & mask)
                    if dut.m_axis_tlast.value:
                        break
            self.ap.write(CpInserterOutputItem(samples))
