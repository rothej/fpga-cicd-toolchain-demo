# verif/nr_chain/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import nr_loopback_check
from verif.nr_chain.monitors import NrChainOutputItem
from verif.nr_chain.seq_item import NrChainSeqItem


class NrChainScoreboard(uvm_component):
    """
    End-to-end scoreboard for the nr_chain loopback testbench.

    TX FIFO: NrChainSeqItem     from driver.ap       (original payload bytes)
    RX FIFO: NrChainOutputItem  from output monitor  (recovered bytes + crc_ok)

    Loopback invariant: rx.data == tx.payload AND rx.crc_ok == True.

    Failure modes (reported in priority order):
      1. CRC failure     - scrambler seed mismatch / QAM demap error / CRC poly bug
      2. Length mismatch - CRC byte stripping wrong, or tlast framing error
      3. Payload mismatch - byte-level difference when length matches; first error
                            index localises the fault to a specific pipeline stage
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export
        self._passed = 0
        self._failed = 0

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._passed = 0
        self._failed = 0
        while True:
            tx: NrChainSeqItem = await self.tx_fifo.get()
            rx: NrChainOutputItem = await self.rx_fifo.get()

            failed = False

            if not rx.crc_ok:
                failed = True
                self.logger.error(
                    f"CRC FAIL {tx}: crc_ok=0 "
                    f"- check scrambler_seed match, CRC polynomial, "
                    f"and QAM demap rounding"
                )

            if len(rx.data) != len(tx.payload):
                failed = True
                delta = len(rx.data) - len(tx.payload)
                self.logger.error(
                    f"Length mismatch {tx}: "
                    f"expected {len(tx.payload)} bytes got {len(rx.data)} "
                    f"({'extra' if delta > 0 else 'missing'} {abs(delta)} byte(s)) "
                    f"- check CRC stripping count (POLY_W/8) and tlast framing"
                )
            elif rx.data != tx.payload:
                failed = True
                errs = [
                    (i, tx.payload[i], rx.data[i])
                    for i in range(len(tx.payload))
                    if tx.payload[i] != rx.data[i]
                ]
                i0, exp0, got0 = errs[0]
                self.logger.error(
                    f"Payload mismatch {tx}: {len(errs)} byte(s) wrong - "
                    f"first at byte[{i0}] exp=0x{exp0:02x} got=0x{got0:02x}"
                )

            # Final guard: catches any future refactor that removes
            # one of the individual checks above.
            if not failed and not nr_loopback_check(tx.payload, rx.data, rx.crc_ok):
                failed = True
                self.logger.error(f"Loopback invariant failed {tx}")

            if failed:
                self._failed += 1
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
