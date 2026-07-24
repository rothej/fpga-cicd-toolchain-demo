# verif/scrambler/driver.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.scrambler.seq_item import ScramblerSeqItem


class ScramblerDriver(uvm_driver):
    """
    AXI4-S master driver for scrambler.sv.

    Per-packet protocol:
      1. Write item.cinit -> dut.cinit; pulse dut.cinit_load for one cycle.
      2. Drive data words onto s_axis_* with tready backpressure.

    Publishes ScramblerSeqItem to ap after the last word is accepted.
    The scoreboard uses these items as its TX reference.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cinit_load.value = 0

        while True:
            item: ScramblerSeqItem = await self.seq_item_port.get_next_item()
            await self._load_cinit(item.cinit)
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)

    async def _load_cinit(self, cinit: int) -> None:
        """Write cinit and pulse cinit_load for exactly one clock cycle."""
        dut = self.dut
        dut.cinit.value = cinit
        dut.cinit_load.value = 1
        await RisingEdge(dut.clk)
        dut.cinit_load.value = 0

    async def _drive(self, item: ScramblerSeqItem) -> None:
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
