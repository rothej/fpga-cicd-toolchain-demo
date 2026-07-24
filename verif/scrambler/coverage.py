# verif/scrambler/coverage.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.scrambler.monitors import ScramblerOutputItem
from verif.scrambler.seq_item import ScramblerSeqItem

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


class ScramblerCoverageCollector(uvm_component):
    """
    Functional coverage for scrambler.sv.

    Dimensions:
        payload_len - four coarse length buckets
        cinit       - one bin per unique cinit exercised
        all_zeros   - at least one all-zero input packet observed
        data_w      - data widths exercised
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export

        self._len_hits: dict[str, int] = {label: 0 for label, *_ in _LEN_BINS}
        self._cinit_hits: dict[int, int] = {}
        self._data_w_hits: dict[int, int] = {}
        self._all_zeros_seen: bool = False

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._len_hits = {label: 0 for label, *_ in _LEN_BINS}
        self._cinit_hits = {}
        self._data_w_hits = {}
        self._all_zeros_seen = False
        while True:
            tx: ScramblerSeqItem = await self.tx_fifo.get()
            _: ScramblerOutputItem = await self.rx_fifo.get()  # consume to stay in sync

            label = _len_bin(len(tx.data))
            self._len_hits[label] = self._len_hits.get(label, 0) + 1
            self._cinit_hits[tx.cinit] = self._cinit_hits.get(tx.cinit, 0) + 1
            self._data_w_hits[tx.data_w] = self._data_w_hits.get(tx.data_w, 0) + 1

            if all(b == 0 for b in tx.data):
                self._all_zeros_seen = True

    def report_phase(self) -> None:
        self.logger.info("=== Scrambler Coverage Report ===")
        for label, count in self._len_hits.items():
            self.logger.info(f"  len  {label}: {count}")
        for cinit, count in self._cinit_hits.items():
            self.logger.info(f"  cinit 0x{cinit:08X}: {count}")
        for dw, count in self._data_w_hits.items():
            self.logger.info(f"  data_w={dw}: {count}")
        self.logger.info(f"  all-zero input seen: {self._all_zeros_seen}")

        if not self._all_zeros_seen:
            self.logger.warning("  Coverage gap: no all-zero input packet sent")
        if len(self._cinit_hits) < 2:
            self.logger.warning("  Coverage gap: fewer than 2 cinit values exercised")
