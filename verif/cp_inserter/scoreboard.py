# verif/cp_inserter/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import cp_insert
from verif.cp_inserter.monitors import CpInserterOutputItem
from verif.cp_inserter.seq_item import CpInserterSeqItem


class CpInserterScoreboard(uvm_component):
    """
    Scoreboard for cp_inserter.sv.

    TX FIFO: CpInserterSeqItem     from driver.ap      (driven samples + cp_len)
    RX FIFO: CpInserterOutputItem  from output monitor (cp_len + N_FFT samples)

    Reference: cp_insert(tx.samples, tx.cp_len) must equal rx.samples.

    Three failure modes reported separately:
      1. Wrong output length (cp_len not applied, or off-by-one on tlast)
      2. CP region wrong    (tail-copy address error)
      3. Payload corrupted  (pipeline flush / inter-symbol contamination)
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
            tx: CpInserterSeqItem = await self.tx_fifo.get()
            rx: CpInserterOutputItem = await self.rx_fifo.get()

            expected = cp_insert(tx.samples, tx.cp_len)

            if len(rx.samples) != len(expected):
                self._failed += 1
                self.logger.error(
                    f"Length mismatch {tx}: "
                    f"expected {len(expected)} "
                    f"(n_fft={len(tx.samples)} + cp_len={tx.cp_len}) "
                    f"got {len(rx.samples)}"
                )
                continue

            cp_errs = [
                (i, expected[i], rx.samples[i])
                for i in range(tx.cp_len)
                if expected[i] != rx.samples[i]
            ]
            pay_errs = [
                (i, expected[i], rx.samples[i])
                for i in range(tx.cp_len, len(expected))
                if expected[i] != rx.samples[i]
            ]

            if cp_errs or pay_errs:
                self._failed += 1
                msg = f"FAIL {tx}:"
                if cp_errs:
                    i, exp, got = cp_errs[0]
                    msg += (
                        f" {len(cp_errs)} CP error(s) - "
                        f"first at out[{i}] "
                        f"exp=0x{exp:04x} got=0x{got:04x};"
                    )
                if pay_errs:
                    i, exp, got = pay_errs[0]
                    msg += (
                        f" {len(pay_errs)} payload error(s) - "
                        f"first at out[{i}] "
                        f"exp=0x{exp:04x} got=0x{got:04x}"
                    )
                self.logger.error(msg)
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
