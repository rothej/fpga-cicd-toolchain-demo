# verif/crc_checker/monitors.py

"""
verif/crc_checker/monitors.py

Passive monitor for crc_checker.sv's crc_pass / crc_fail output.

crc_pass and crc_fail are mutually exclusive single-cycle pulses defined
in crc_checker.sv:
    crc_pass - pulsed one cycle after last when computed CRC == crc_ref
    crc_fail - pulsed one cycle after last when computed CRC != crc_ref

One CrcStatusItem is published to ap per pulse observed.
"""

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component


class CrcStatusItem:
    """Single CRC check result sampled from crc_checker.sv output."""

    __slots__ = ("crc_ok",)

    def __init__(self, crc_ok: bool) -> None:
        self.crc_ok = crc_ok

    def __repr__(self) -> str:
        return f"CrcStatusItem(crc_ok={self.crc_ok})"


class CrcStatusMonitor(uvm_component):
    """
    Passively samples crc_pass and crc_fail on rising clock edges.

    On each rising edge where crc_pass is asserted a CrcStatusItem(crc_ok=True)
    is published.  On each rising edge where crc_fail is asserted a
    CrcStatusItem(crc_ok=False) is published.  The two signals are mutually
    exclusive by RTL construction so at most one item fires per cycle.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")

    async def run_phase(self) -> None:
        dut = self.dut
        while True:
            await RisingEdge(dut.clk)
            if dut.crc_pass.value:
                self.ap.write(CrcStatusItem(crc_ok=True))
            elif dut.crc_fail.value:
                self.ap.write(CrcStatusItem(crc_ok=False))
