# verif/qam_mapper/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from verif.common.config_utils import _cfg


def _sign_extend(val: int, width: int) -> int:
    """Two's-complement sign-extension of an unsigned integer."""
    if val >= (1 << (width - 1)):
        val -= 1 << width
    return val


class QamMapperOutputItem:
    """One complete mapped packet: a list of (I, Q) symbol pairs."""

    def __init__(self, symbols: list[tuple[int, int]]) -> None:
        self.symbols = symbols

    def __repr__(self) -> str:
        return f"QamMapperOutputItem(n_symbols={len(self.symbols)})"


class QamMapperOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on qam_mapper.sv's m_axis_* output.

    m_axis_tdata layout (default IQ_W=8, total 16 bits):
        [15:8]  I  (signed)
        [ 7:0]  Q  (signed)

    Holds m_axis_tready=1 continuously - no output backpressure.
    Publishes one QamMapperOutputItem per tlast-terminated packet.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.iq_w = _cfg(self, "iq_w", 8)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.m_axis_tready.value = 1

        while True:
            symbols: list[tuple[int, int]] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    tdata = int(dut.m_axis_tdata.value)
                    mask = (1 << self.iq_w) - 1
                    i_val = _sign_extend((tdata >> self.iq_w) & mask, self.iq_w)
                    q_val = _sign_extend(tdata & mask, self.iq_w)
                    symbols.append((i_val, q_val))
                    if dut.m_axis_tlast.value:
                        break
            self.ap.write(QamMapperOutputItem(symbols))
