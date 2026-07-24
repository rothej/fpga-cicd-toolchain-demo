# verif/nr_chain/driver.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.common.config_utils import _cfg
from verif.nr_chain.seq_item import NrChainSeqItem


class NrChainDriver(uvm_driver):
    """
    AXI4-S master driver for nr_chain_top's byte-level input.

    Protocol per transport block:
      1. Present cp_len and scrambler_seed one cycle before tvalid.
      2. Drive each payload byte on s_axis_tdata with tready backpressure.
      3. Assert tlast on the final payload byte (CRC is appended internally
         by the TX chain - the driver does not transmit CRC bytes).

    Publishes NrChainSeqItem to ap after the last byte is accepted.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.data_w = _cfg(self, "data_w", 8)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0
        dut.scrambler_seed.value = 0

        while True:
            item: NrChainSeqItem = await self.seq_item_port.get_next_item()
            await self._set_sideband(item)
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)

    async def _set_sideband(self, item: NrChainSeqItem) -> None:
        """Present cp_len and scrambler_seed one setup cycle before tvalid."""
        self.dut.cp_len.value = item.cp_len
        self.dut.scrambler_seed.value = item.scrambler_seed
        await RisingEdge(self.dut.clk)

    async def _drive(self, item: NrChainSeqItem) -> None:
        dut = self.dut
        mask = (1 << self.data_w) - 1
        last = len(item.payload) - 1

        for idx, byte_val in enumerate(item.payload):
            dut.s_axis_tdata.value = byte_val & mask
            dut.s_axis_tvalid.value = 1
            dut.s_axis_tlast.value = int(idx == last)
            await RisingEdge(dut.clk)
            while not dut.s_axis_tready.value:
                await RisingEdge(dut.clk)

        dut.s_axis_tvalid.value = 0
        dut.s_axis_tlast.value = 0
