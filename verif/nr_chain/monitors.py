# verif/nr_chain/monitors.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component

from verif.common.config_utils import _cfg


class NrChainOutputItem:
    """One recovered transport block from the RX chain output."""

    def __init__(self, data: list[int]) -> None:
        self.data = data

    def __repr__(self) -> str:
        return f"NrChainOutputItem(len={len(self.data)})"


class NrChainLoopbackItem:
    """
    One transport block's worth of OFDM samples observed at the TX->RX boundary.

    tlast only marks the end of a block (not of each symbol), so a multi-symbol
    block arrives as a single item of n_symbols * (N_FFT + cp_len) samples.

    user_idx - indices into samples where lb_tuser was high (block-start tag)
    """

    def __init__(self, samples: list[int], user_idx: list[int]) -> None:
        self.samples = samples
        self.user_idx = user_idx

    def n_symbols(self, n_fft: int, cp_len: int) -> int | None:
        """Whole OFDM symbols in this block, or None if the length isn't a multiple."""
        q, r = divmod(len(self.samples), n_fft + cp_len)
        return q if r == 0 else None

    def __repr__(self) -> str:
        return f"NrChainLoopbackItem(n_samples={len(self.samples)}, user_idx={self.user_idx})"


class NrChainOutputMonitor(uvm_component):
    """
    Passive AXI4-S slave monitor on nr_chain_top's byte-level RX output.

    Holds m_axis_tready=1 continuously (no TB-side backpressure).
    Collects DATA_W-bit bytes per accepted beat;
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
            while True:
                await RisingEdge(dut.clk)
                if dut.m_axis_tvalid.value and dut.m_axis_tready.value:
                    data.append(int(dut.m_axis_tdata.value) & mask)
                    if dut.m_axis_tlast.value:
                        break
            self.ap.write(NrChainOutputItem(data))


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
            user_idx: list[int] = []
            while True:
                await RisingEdge(dut.clk)
                if dut.lb_tvalid.value and dut.lb_tready.value:
                    if dut.lb_tuser.value:
                        user_idx.append(len(samples))
                    samples.append(int(dut.lb_tdata.value) & mask)
                    if dut.lb_tlast.value:
                        break
            self.ap.write(NrChainLoopbackItem(samples, user_idx))
