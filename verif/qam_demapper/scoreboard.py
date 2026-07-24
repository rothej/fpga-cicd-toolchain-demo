# verif/qam_demapper/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import qam_demap
from verif.qam_demapper.monitors import QamDemapperOutputItem
from verif.qam_demapper.seq_item import QamDemapperSeqItem


class QamDemapperScoreboard(uvm_component):
    """
    Scoreboard for qam_demapper.sv.

    TX FIFO: QamDemapperSeqItem    from driver.ap  (I/Q symbols driven)
    RX FIFO: QamDemapperOutputItem from QamDemapperOutputMonitor.ap

    Reference: qam_demap(tx.symbols, tx.mod_order) must equal rx.words.
    First mismatching word index, expected, and actual are logged on failure.
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
            tx: QamDemapperSeqItem = await self.tx_fifo.get()
            rx: QamDemapperOutputItem = await self.rx_fifo.get()

            expected = qam_demap(tx.symbols, tx.mod_order)

            if len(rx.words) != len(expected):
                self._failed += 1
                self.logger.error(
                    f"Word count mismatch: expected {len(expected)} got {len(rx.words)}  {tx}"
                )
                continue

            mismatches = [
                (i, expected[i], rx.words[i])
                for i in range(len(expected))
                if expected[i] != rx.words[i]
            ]

            if mismatches:
                self._failed += 1
                i, exp, got = mismatches[0]
                self.logger.error(
                    f"FAIL {tx}: {len(mismatches)} mismatch(es) - "
                    f"first at word[{i}] "
                    f"exp=0x{exp:0{tx.mod_order // 4}x} "
                    f"got=0x{got:0{tx.mod_order // 4}x}"
                )
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
