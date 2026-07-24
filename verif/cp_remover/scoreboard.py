# verif/cp_remover/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.nr_ref_model import cp_remove
from verif.cp_remover.monitors import CpRemoverOutputItem
from verif.cp_remover.seq_item import CpRemoverSeqItem


class CpRemoverScoreboard(uvm_component):
    """
    Scoreboard for cp_remover.sv.

    TX FIFO: CpRemoverSeqItem     from driver.ap      (full packet + cp_len)
    RX FIFO: CpRemoverOutputItem  from output monitor (N_FFT output samples)

    Reference: cp_remove(tx.full_samples, tx.cp_len) must equal rx.samples.

    Three failure modes reported separately:
      1. Wrong output length  (CP not discarded, or tlast misplaced)
      2. Leading-sample wrong (fence-post error on the discard counter)
      3. Payload corrupted    (pipeline flush / inter-symbol contamination)
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
            tx: CpRemoverSeqItem = await self.tx_fifo.get()
            rx: CpRemoverOutputItem = await self.rx_fifo.get()

            expected = cp_remove(tx.full_samples, tx.cp_len)

            if len(rx.samples) != len(expected):
                self._failed += 1
                self.logger.error(
                    f"Length mismatch {tx}: "
                    f"expected {len(expected)} (n_fft={tx.n_fft}) "
                    f"got {len(rx.samples)} "
                    f"- cp_len={tx.cp_len} samples "
                    f"{'not discarded' if len(rx.samples) > len(expected) else 'over-discarded'}"
                )
                continue

            errs = [
                (i, expected[i], rx.samples[i])
                for i in range(len(expected))
                if expected[i] != rx.samples[i]
            ]

            if errs:
                self._failed += 1
                i0, exp0, got0 = errs[0]
                fence_post = i0 == 0
                fence_msg = (
                    " - leading-sample wrong (fence-post on discard counter?)" if fence_post else ""
                )
                msg = (
                    f"FAIL {tx}: {len(errs)} mismatch(es)"
                    + fence_msg
                    + f" - first at out[{i0}] exp=0x{exp0:04x} got=0x{got0:04x}"
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
