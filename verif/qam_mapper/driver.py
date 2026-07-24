# verif/qam_mapper/driver.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.qam_mapper.seq_item import QamMapperSeqItem


class QamMapperDriver(uvm_driver):
    """
    AXI4-S master driver for qam_mapper.sv.

    Per-packet protocol:
      1. Write item.mod_order -> dut.mod_order; wait one clock cycle.
      2. Drive data words onto s_axis_* with tready backpressure.

    Publishes QamMapperSeqItem to ap after the last word is accepted.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.mod_order.value = 2  # idle: QPSK

        while True:
            item: QamMapperSeqItem = await self.seq_item_port.get_next_item()
            await self._set_mod_order(item.mod_order)
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)

    async def _set_mod_order(self, mod_order: int) -> None:
        """Assert mod_order one cycle before the first data beat."""
        self.dut.mod_order.value = mod_order
        await RisingEdge(self.dut.clk)

    async def _drive(self, item: QamMapperSeqItem) -> None:
        dut = self.dut
        for idx, word in enumerate(item.data):
            is_last = idx == len(item.data) - 1
            dut.s_axis_tdata.value = word
            dut.s_axis_tvalid.value = 1
            dut.s_axis_tlast.value = int(is_last)
            await RisingEdge(dut.clk)
            while not dut.s_axis_tready.value:
                await RisingEdge(dut.clk)

        dut.s_axis_tvalid.value = 0
        dut.s_axis_tlast.value = 0
