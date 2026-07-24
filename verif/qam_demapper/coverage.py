# verif/qam_demapper/coverage.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.qam_demapper.monitors import QamDemapperOutputItem
from verif.qam_demapper.seq_item import QamDemapperSeqItem

_MO_NAMES = {2: "QPSK", 4: "16-QAM", 6: "64-QAM", 8: "256-QAM"}

_LEN_BINS: list[tuple[str, int, int]] = [
    ("tiny   [1,8)", 1, 8),
    ("small  [8,64)", 8, 64),
    ("medium [64,256)", 64, 256),
    ("large  [256,+)", 256, 2**31),
]


def _len_bin(n: int) -> str:
    for label, lo, hi in _LEN_BINS:
        if lo <= n < hi:
            return label
    return f"xlarge [{n})"


class QamDemapperCoverageCollector(uvm_component):
    """
    Functional coverage for qam_demapper.sv.

    Dimensions:
        mod_order      - 4 bins: QPSK / 16-QAM / 64-QAM / 256-QAM
        input_constell - unique (I, Q) pairs driven per mod_order
        output_words   - unique recovered data words seen per mod_order
        payload_len    - four coarse packet-length buckets (in symbols)
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export

        self._mo_hits: dict[int, int] = {mo: 0 for mo in (2, 4, 6, 8)}
        self._len_hits: dict[str, int] = {label: 0 for label, *_ in _LEN_BINS}
        self._in_constell: dict[int, set[tuple[int, int]]] = {mo: set() for mo in (2, 4, 6, 8)}
        self._out_words: dict[int, set[int]] = {mo: set() for mo in (2, 4, 6, 8)}

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._mo_hits = {mo: 0 for mo in (2, 4, 6, 8)}
        self._len_hits = {label: 0 for label, *_ in _LEN_BINS}
        self._in_constell = {mo: set() for mo in (2, 4, 6, 8)}
        self._out_words = {mo: set() for mo in (2, 4, 6, 8)}
        while True:
            tx: QamDemapperSeqItem = await self.tx_fifo.get()
            rx: QamDemapperOutputItem = await self.rx_fifo.get()

            mo = tx.mod_order
            label = _len_bin(len(tx.symbols))

            self._mo_hits[mo] = self._mo_hits.get(mo, 0) + 1
            self._len_hits[label] = self._len_hits.get(label, 0) + 1
            self._in_constell[mo].update(tx.symbols)
            self._out_words[mo].update(rx.words)

    def report_phase(self) -> None:
        self.logger.info("=== QAM Demapper Coverage Report ===")
        for mo in (2, 4, 6, 8):
            name = _MO_NAMES[mo]
            n_possible = 1 << mo
            n_in = len(self._in_constell[mo])
            n_out = len(self._out_words[mo])
            self.logger.info(
                f"  {name:8s}: {self._mo_hits[mo]} pkts | "
                f"in-constell {n_in}/{n_possible} "
                f"({100 * n_in // n_possible}%) | "
                f"out-words {n_out}/{n_possible} "
                f"({100 * n_out // n_possible}%)"
            )
            if self._mo_hits[mo] == 0:
                self.logger.warning(f"  Coverage gap: {name} never exercised")

        self.logger.info("  Packet length distribution (symbols):")
        for label, count in self._len_hits.items():
            self.logger.info(f"    {label}: {count}")
