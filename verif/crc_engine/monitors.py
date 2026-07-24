# verif/crc_engine/monitors.py

"""
verif/crc_engine/monitors.py

Passive monitor for crc_engine.sv's crc_out / crc_valid output.

crc_valid is a single-cycle pulse asserted exactly one clock after the
final data_valid && last beat. One CrcResultTransaction is published per
pulse.
"""

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component, uvm_sequence_item

__all__ = ["CrcResultTransaction", "CrcOutputMonitor"]


class CrcResultTransaction(uvm_sequence_item):
    """Carries one CRC output value captured from the DUT."""

    def __init__(self, name: str = "CrcResultTransaction") -> None:
        super().__init__(name)
        self.crc_value: int = 0

    def __repr__(self) -> str:
        return f"CrcResultTransaction(crc_value=0x{self.crc_value:06X})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CrcResultTransaction):
            return NotImplemented
        return self.crc_value == other.crc_value


class CrcOutputMonitor(uvm_component):
    """
    Passively samples crc_out on every rising edge where crc_valid is high.

    One CrcResultTransaction is written to ap per crc_valid assertion.
    crc_engine.sv holds crc_valid high for exactly one cycle after the
    last input byte is consumed.
    """

    def build_phase(self) -> None:
        self.ap: uvm_analysis_port = uvm_analysis_port("ap", self)

    def start_of_simulation_phase(self) -> None:
        dut = ConfigDB().get(self, "", "dut")
        self._clk = dut.clk
        self._crc_out = dut.crc_out
        self._crc_valid = dut.crc_valid

    async def run_phase(self) -> None:
        while True:
            await RisingEdge(self._clk)
            if int(self._crc_valid.value) == 1:
                txn = CrcResultTransaction()
                txn.crc_value = int(self._crc_out.value)
                self.ap.write(txn)
