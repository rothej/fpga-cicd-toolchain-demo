# verif/cp_remover/coverage.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.cp_remover.monitors import CpRemoverOutputItem
from verif.cp_remover.seq_item import CpRemoverSeqItem

_CP_BINS: list[tuple[str, int, int]] = [
    ("zero    [0]", 0, 1),
    ("short   [1,8)", 1, 8),
    ("medium  [8,32)", 8, 32),
    ("long    [32,+)", 32, 2**31),
]


def _cp_bin(cp_len: int) -> str:
    for label, lo, hi in _CP_BINS:
        if lo <= cp_len < hi:
            return label
    return f"xlarge [{cp_len})"


class CpRemoverCoverageCollector(uvm_component):
    """
    Functional coverage for cp_remover.sv.

    Dimensions:
        cp_len_bins  - four coarse CP length buckets
        n_fft_vals   - unique FFT sizes seen
        cp_len_vals  - every distinct cp_len value driven
        symbol_count - total packets processed
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export

        self._cp_bin_hits: dict[str, int] = {label: 0 for label, *_ in _CP_BINS}
        self._n_fft_vals: set[int] = set()
        self._cp_len_vals: set[int] = set()
        self._symbol_count: int = 0

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._cp_bin_hits = {label: 0 for label, *_ in _CP_BINS}
        self._n_fft_vals = set()
        self._cp_len_vals = set()
        self._symbol_count = 0
        while True:
            tx: CpRemoverSeqItem = await self.tx_fifo.get()
            _rx: CpRemoverOutputItem = await self.rx_fifo.get()  # sync only

            label = _cp_bin(tx.cp_len)
            self._cp_bin_hits[label] = self._cp_bin_hits.get(label, 0) + 1
            self._n_fft_vals.add(tx.n_fft)
            self._cp_len_vals.add(tx.cp_len)
            self._symbol_count += 1

    def report_phase(self) -> None:
        self.logger.info("=== CP Remover Coverage Report ===")
        self.logger.info(f"  Total packets  : {self._symbol_count}")
        self.logger.info(f"  N_FFT values   : {sorted(self._n_fft_vals)}")
        self.logger.info(f"  cp_len values  : {sorted(self._cp_len_vals)}")
        self.logger.info("  CP length distribution:")
        for label, count in self._cp_bin_hits.items():
            self.logger.info(f"    {label}: {count}")
        if 0 not in self._cp_len_vals:
            self.logger.warning("  Coverage gap: cp_len=0 (passthrough) never exercised")
