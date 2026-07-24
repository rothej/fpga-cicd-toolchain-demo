# verif/scrambler/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import scramble
from verif.scrambler.monitors import ScramblerOutputItem
from verif.scrambler.seq_item import ScramblerSeqItem


class ScramblerScoreboard(uvm_component):
    """
    Scoreboard for scrambler.sv.

    TX FIFO: ScramblerSeqItem  from driver.ap
    RX FIFO: ScramblerOutputItem from ScramblerOutputMonitor.ap

    Reference: scramble(tx.data, tx.cinit, tx.data_w) must equal rx.data.
    First mismatching word index and value are logged on failure.
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
            tx: ScramblerSeqItem = await self.tx_fifo.get()
            rx: ScramblerOutputItem = await self.rx_fifo.get()

            expected = scramble(tx.data, tx.cinit, tx.data_w)

            if len(rx.data) != len(expected):
                self._failed += 1
                self.logger.error(
                    f"Length mismatch: expected {len(expected)} words got {len(rx.data)}  {tx}"
                )
                continue

            mismatches = [
                (i, expected[i], rx.data[i])
                for i in range(len(expected))
                if expected[i] != rx.data[i]
            ]

            if mismatches:
                self._failed += 1
                i, exp, got = mismatches[0]
                self.logger.error(
                    f"FAIL {tx}: {len(mismatches)} mismatch(es) - "
                    f"first at word[{i}] exp=0x{exp:X} got=0x{got:X}"
                )
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
