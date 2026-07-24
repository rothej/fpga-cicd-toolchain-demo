# verif/qam_mapper/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import qam_map
from verif.qam_mapper.monitors import QamMapperOutputItem
from verif.qam_mapper.seq_item import QamMapperSeqItem


class QamMapperScoreboard(uvm_component):
    """
    Scoreboard for qam_mapper.sv.

    TX FIFO: QamMapperSeqItem    from driver.ap
    RX FIFO: QamMapperOutputItem from QamMapperOutputMonitor.ap

    Reference: qam_map(tx.data, tx.mod_order) must equal rx.symbols.
    First mismatching symbol index, expected, and actual are logged on failure.
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
            tx: QamMapperSeqItem = await self.tx_fifo.get()
            rx: QamMapperOutputItem = await self.rx_fifo.get()

            expected = qam_map(tx.data, tx.mod_order)

            if len(rx.symbols) != len(expected):
                self._failed += 1
                self.logger.error(
                    f"Symbol count mismatch: expected {len(expected)} got {len(rx.symbols)}  {tx}"
                )
                continue

            mismatches = [
                (i, expected[i], rx.symbols[i])
                for i in range(len(expected))
                if expected[i] != rx.symbols[i]
            ]

            if mismatches:
                self._failed += 1
                i, exp, got = mismatches[0]
                self.logger.error(
                    f"FAIL {tx}: {len(mismatches)} mismatch(es) - "
                    f"first at sym[{i}] exp={exp} got={got}"
                )
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
