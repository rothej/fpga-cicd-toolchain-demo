# verif/crc_checker/scoreboard.py

"""
verif/crc_checker/scoreboard.py

Scoreboard for crc_checker.sv.

TX FIFO: CrcCheckerSeqItem  from driver.ap      (payload + corrupt flag)
RX FIFO: CrcStatusItem      from CrcStatusMonitor.ap  (crc_pass / crc_fail)

Correctness invariant:
    item.corrupt == False  →  expect rx.crc_ok == True  (crc_pass pulsed)
    item.corrupt == True   →  expect rx.crc_ok == False (crc_fail pulsed)
"""

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.crc_checker.monitors import CrcStatusItem
from verif.crc_checker.seq_item import CrcCheckerSeqItem


class CrcCheckerScoreboard(uvm_component):
    """
    Compares DUT crc_pass / crc_fail output against the expected outcome.

    The expected outcome is determined solely by the corrupt flag in the
    seq_item — the scoreboard does not re-compute the CRC polynomial.
    Polynomial correctness is validated transitively: if the sequence
    computes the right CRC and the DUT agrees, both are correct; if they
    disagree, the mismatch surfaces as a scoreboard failure.
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
            tx: CrcCheckerSeqItem = await self.tx_fifo.get()
            rx: CrcStatusItem = await self.rx_fifo.get()

            expected_ok = not tx.corrupt

            if rx.crc_ok == expected_ok:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")
            else:
                self._failed += 1
                pulse = "crc_pass" if rx.crc_ok else "crc_fail"
                self.logger.error(
                    f"FAIL {tx}: "
                    f"expected crc_ok={expected_ok} "
                    f"got crc_ok={rx.crc_ok} "
                    f"({pulse} pulsed)"
                )

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
