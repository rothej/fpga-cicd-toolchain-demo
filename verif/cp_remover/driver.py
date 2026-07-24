# verif/cp_remover/driver.py

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.common.config_utils import _cfg
from verif.cp_remover.seq_item import CpRemoverSeqItem


class CpRemoverDriver(uvm_driver):
    """
    AXI4-Stream master driver for cp_remover.sv.

    Protocol per packet:
      1. Assert item.cp_len -> dut.cp_len; wait one setup cycle.
      2. Drive all (cp_len + N_FFT) samples on s_axis_* with tready backpressure.
      3. Assert tlast on the final sample beat (beat cp_len + N_FFT - 1).

    Publishes CpRemoverSeqItem to ap after the last input sample is accepted.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.samp_w = _cfg(self, "samp_w", 16)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0

        while True:
            item: CpRemoverSeqItem = await self.seq_item_port.get_next_item()
            await self._set_cp_len(item.cp_len)
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)

    async def _set_cp_len(self, cp_len: int) -> None:
        """Assert cp_len one cycle before the first tvalid beat."""
        self.dut.cp_len.value = cp_len
        await RisingEdge(self.dut.clk)

    async def _drive(self, item: CpRemoverSeqItem) -> None:
        dut = self.dut
        mask = (1 << self.samp_w) - 1
        last = len(item.full_samples) - 1

        for idx, sample in enumerate(item.full_samples):
            dut.s_axis_tdata.value = sample & mask
            dut.s_axis_tvalid.value = 1
            dut.s_axis_tlast.value = int(idx == last)
            await RisingEdge(dut.clk)
            while not dut.s_axis_tready.value:
                await RisingEdge(dut.clk)

        dut.s_axis_tvalid.value = 0
        dut.s_axis_tlast.value = 0
