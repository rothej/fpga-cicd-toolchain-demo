# verif/qam_demapper/driver.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.common.config_utils import _cfg
from verif.qam_demapper.seq_item import QamDemapperSeqItem


class QamDemapperDriver(uvm_driver):
    """
    AXI4-S master driver for qam_demapper.sv.

    tdata packing (matches qam_mapper.sv output):
        s_axis_tdata = { I[IQ_W-1:0], Q[IQ_W-1:0] }   (I in upper half)

    Negative I/Q levels are packed as unsigned two's complement via & mask.

    Per-packet protocol:
      1. Write item.mod_order -> dut.mod_order; wait one clock cycle.
      2. Drive (I, Q) pairs onto s_axis_* with tready backpressure.

    Publishes QamDemapperSeqItem to ap after the last symbol is accepted.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.iq_w = _cfg(self, "iq_w", 8)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.mod_order.value = 2

        while True:
            item: QamDemapperSeqItem = await self.seq_item_port.get_next_item()
            await self._set_mod_order(item.mod_order)
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)

    async def _set_mod_order(self, mod_order: int) -> None:
        """Assert mod_order one cycle before the first symbol beat."""
        self.dut.mod_order.value = mod_order
        await RisingEdge(self.dut.clk)

    async def _drive(self, item: QamDemapperSeqItem) -> None:
        dut = self.dut
        mask = (1 << self.iq_w) - 1

        for idx, (i_val, q_val) in enumerate(item.symbols):
            is_last = idx == len(item.symbols) - 1
            i_bits = i_val & mask  # 2's complement truncation
            q_bits = q_val & mask
            dut.s_axis_tdata.value = (i_bits << self.iq_w) | q_bits
            dut.s_axis_tvalid.value = 1
            dut.s_axis_tlast.value = int(is_last)
            await RisingEdge(dut.clk)
            while not dut.s_axis_tready.value:
                await RisingEdge(dut.clk)

        dut.s_axis_tvalid.value = 0
        dut.s_axis_tlast.value = 0
