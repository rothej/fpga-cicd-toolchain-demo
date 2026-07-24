# verif/crc_checker/coverage.py

"""
verif/crc_checker/coverage.py

Functional coverage collector for crc_checker.sv.
"""

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.crc_checker.monitors import CrcStatusItem
from verif.crc_checker.seq_item import _CRCTYPE_NAMES, CrcCheckerSeqItem

_LEN_BINS: list[tuple[str, int, int]] = [
    ("tiny   [1,4)", 1, 4),
    ("small  [4,16)", 4, 16),
    ("medium [16,64)", 16, 64),
    ("large  [64,256)", 64, 256),
]


def _len_bin(n: int) -> str:
    for label, lo, hi in _LEN_BINS:
        if lo <= n < hi:
            return label
    return f"xlarge [{n})"


class CrcCoverageCollector(uvm_component):
    """
    Functional coverage for crc_checker.sv.

    Coverage dimensions:
        payload_len  - four coarse buckets
        crc_type     - one bin per crc_type_e value seen
        corrupt      - True / False
        cross        - (corrupt, crc_ok) - all four cells should be hit:
                       (False, True)  - valid CRC, crc_pass fires
                       (True,  False) - corrupt CRC, crc_fail fires
                       (False, False) - wrong polynomial - indicates a bug
                       (True,  True)  - corrupt CRC passes - indicates a bug

    Report is emitted to the log at report_phase; missing cross cells are
    flagged explicitly so CI can grep for them.
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export

        self._len_hits: dict[str, int] = {label: 0 for label, *_ in _LEN_BINS}
        self._type_hits: dict[int, int] = {}
        self._corrupt_hits: dict[bool, int] = {False: 0, True: 0}
        self._cross_hits: dict[tuple, int] = {}

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._len_hits = {label: 0 for label, *_ in _LEN_BINS}
        self._type_hits = {}
        self._corrupt_hits = {False: 0, True: 0}
        self._cross_hits = {}
        while True:
            tx: CrcCheckerSeqItem = await self.tx_fifo.get()
            rx: CrcStatusItem = await self.rx_fifo.get()

            label = _len_bin(len(tx.payload))
            self._len_hits[label] = self._len_hits.get(label, 0) + 1
            self._type_hits[tx.crc_type] = self._type_hits.get(tx.crc_type, 0) + 1
            self._corrupt_hits[tx.corrupt] += 1

            key = (tx.corrupt, rx.crc_ok)
            self._cross_hits[key] = self._cross_hits.get(key, 0) + 1

    def report_phase(self) -> None:
        self.logger.info("=== CrcChecker Coverage Report ===")

        for label, count in self._len_hits.items():
            self.logger.info(f"  len  {label}: {count}")

        for crc_type, count in self._type_hits.items():
            name = _CRCTYPE_NAMES.get(crc_type, f"type{crc_type}")
            self.logger.info(f"  crc_type {name}: {count}")

        for flag, count in self._corrupt_hits.items():
            self.logger.info(f"  corrupt={flag}: {count}")

        for (corrupt, ok), count in self._cross_hits.items():
            self.logger.info(f"  cross corrupt={corrupt} crc_ok={ok}: {count}")

        # Expected cross cells — anything else indicates a DUT bug.
        for cell in [(False, True), (True, False)]:
            if not self._cross_hits.get(cell, 0):
                self.logger.warning(f"  Coverage gap: cross cell {cell} never hit")
