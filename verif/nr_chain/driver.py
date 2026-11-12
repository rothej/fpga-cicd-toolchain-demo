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
      3. Assert tlast on the final payload byte.
      4. Wait for m_axis_tlast at the RX output before releasing the item.
         This holds scrambler_seed stable until the RX descrambler has
         finished processing the block - the sideband must remain valid
         from TX cinit_load through RX cinit_load.

    Publishes NrChainSeqItem to ap after m_axis_tlast confirms the block
    has fully exited the RX chain.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")
        self.data_w = _cfg(self, "data_w", 8)
        self.n_fft = _cfg(self, "n_fft", 64)

    async def run_phase(self) -> None:
        dut = self.dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value = 0
        dut.s_axis_tlast.value = 0
        dut.cp_len.value = 0
        dut.scrambler_seed.value = 0

        while True:
            item: NrChainSeqItem = await self.seq_item_port.get_next_item()
            self._check_whole_symbols(item)
            await self._set_sideband(item)
            await self._drive(item)
            await self._wait_for_rx_output()  # hold seed until block exits RX chain
            self.seq_item_port.item_done()
            self.ap.write(item)

    def _check_whole_symbols(self, item: NrChainSeqItem) -> None:
        if not item.payload or len(item.payload) % self.n_fft:
            raise ValueError(
                f"{item}: payload_len must be a non-zero multiple of N_FFT={self.n_fft}. "
                "nr_tx_chain neither pads nor carries a length, so a short block would be "
                "emitted as a full symbol containing stale samples."
            )

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
            while True:
                await RisingEdge(dut.clk)
                if int(dut.s_axis_tready.value):
                    break

        dut.s_axis_tvalid.value = 0
        dut.s_axis_tlast.value = 0

    async def _wait_for_rx_output(self) -> None:
        """
        Block until m_axis_tlast pulses at the RX output.

        Uses a per-cycle poll to avoid
        cocotb 2.0 First/Timer cancellation bugs that cause phantom
        50 000-ns timeouts and silently kill the driver task.
        """
        dut = self.dut
        max_cycles = 100_000
        for _ in range(max_cycles):
            await RisingEdge(dut.clk)
            if (
                int(dut.m_axis_tvalid.value)
                and int(dut.m_axis_tready.value)
                and int(dut.m_axis_tlast.value)
            ):
                return
        raise RuntimeError(
            "[NrChainDriver] m_axis_tlast not seen within "
            f"{max_cycles} cycles — RX chain appears stuck"
        )
