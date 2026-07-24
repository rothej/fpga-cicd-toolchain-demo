# verif/qam_mapper/coverage.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.qam_mapper.monitors import QamMapperOutputItem
from verif.qam_mapper.seq_item import QamMapperSeqItem

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


class QamMapperCoverageCollector(uvm_component):
    """
    Functional coverage for qam_mapper.sv.

    Dimensions:
        mod_order     - 4 bins: QPSK / 16-QAM / 64-QAM / 256-QAM
        constellation - unique (I, Q) pairs observed per mod_order (from DUT output)
        payload_len   - four coarse length buckets (in symbols)
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export

        self._mo_hits: dict[int, int] = {mo: 0 for mo in (2, 4, 6, 8)}
        self._len_hits: dict[str, int] = {label: 0 for label, *_ in _LEN_BINS}
        self._constellation: dict[int, set[tuple[int, int]]] = {mo: set() for mo in (2, 4, 6, 8)}

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._mo_hits = {mo: 0 for mo in (2, 4, 6, 8)}
        self._len_hits = {label: 0 for label, *_ in _LEN_BINS}
        self._constellation = {mo: set() for mo in (2, 4, 6, 8)}
        while True:
            tx: QamMapperSeqItem = await self.tx_fifo.get()
            rx: QamMapperOutputItem = await self.rx_fifo.get()

            mo = tx.mod_order
            label = _len_bin(len(rx.symbols))

            self._mo_hits[mo] = self._mo_hits.get(mo, 0) + 1
            self._len_hits[label] = self._len_hits.get(label, 0) + 1
            self._constellation[mo].update(rx.symbols)

    def report_phase(self) -> None:
        self.logger.info("=== QAM Mapper Coverage Report ===")
        for mo in (2, 4, 6, 8):
            name = _MO_NAMES[mo]
            n_possible = 1 << mo
            n_seen = len(self._constellation[mo])
            pct = 100 * n_seen // n_possible
            self.logger.info(
                f"  {name:8s}: {self._mo_hits[mo]} pkts, "
                f"constellation {n_seen}/{n_possible} pts ({pct}%)"
            )
            if self._mo_hits[mo] == 0:
                self.logger.warning(f"  Coverage gap: {name} never exercised")

        self.logger.info("  Packet length distribution (symbols):")
        for label, count in self._len_hits.items():
            self.logger.info(f"    {label}: {count}")
