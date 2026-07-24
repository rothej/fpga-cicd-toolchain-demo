# verif/nr_chain/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from verif.common.config_utils import _cfg


class NrChainOutputItem:
    """
    One recovered transport block from the RX chain output.

    data   - recovered bytes (expected to equal the original payload)
    crc_ok - DUT's CRC check result, sampled at the tlast beat
    """

    def __init__(self, data: list[int], crc_ok: bool) -> None:
        self.data = data
        self.crc_ok = crc_ok

    def __repr__(self) -> str:
        return f"NrChainOutputItem(len={len(self.data)}, crc_ok={self.crc_ok})"


class NrChainLoopbackItem:
    """One OFDM symbol packet observed at the TX->RX boundary."""

    def __init__(self, samples: list[int]) -> None:
        self.samples = samples

    def __repr__(self) -> str:
        return f"NrChainLoopbackItem(n_samples={len(self.samples)})"


class NrChainOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on nr_chain_top's byte-level RX output.

    Holds m_axis_tready=1 continuously (no TB-side backpressure).
    Collects DATA_W-bit bytes per accepted beat; samples crc_ok at tlast;
    publishes one NrChainOutputItem per tlast-terminated transport block.
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
            data: list[int] = []
            crc_ok = False
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    data.append(int(dut.m_axis_tdata.value) & mask)
                    if dut.m_axis_tlast.value:
                        crc_ok = bool(dut.crc_ok.value)
                        break
            self.ap.write(NrChainOutputItem(data, crc_ok))


class NrChainLoopbackMonitor(uvm_component):
    """
    Passive monitor at the TX->RX boundary (lb_* ports of nr_chain_top).

    Observes OFDM sample flow for coverage purposes only - does not drive
    lb_tready (driven by u_rx). Publishes one NrChainLoopbackItem per
    tlast-terminated OFDM packet.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.samp_w = _cfg(self, "samp_w", 16)

    async def run_phase(self) -> None:
        dut = self.dut
        mask = (1 << self.samp_w) - 1

        while True:
            samples: list[int] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.lb_tvalid.value and dut.lb_tready.value:
                    samples.append(int(dut.lb_tdata.value) & mask)
                    if dut.lb_tlast.value:
                        break
            self.ap.write(NrChainLoopbackItem(samples))
