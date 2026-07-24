# verif/crc_engine/coverage.py

"""
verif/crc_engine/coverage.py

Functional coverage collector for crc_engine.sv.
"""

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.axis_agent import AxisTransaction

__all__ = ["CrcCoverageCollector"]


class CrcCoverageCollector(uvm_component):
    """
    Functional coverage for the crc_engine testbench.

    Receives AxisTransactions from the TX monitor and samples two groups:

        payload_len_bins:
            "single_byte"   - len == 1
            "short_2_7"     - 2   <= len <= 7
            "medium_8_63"   - 8   <= len <= 63
            "long_64_127"   - 64  <= len <= 127
            "max_128_255"   - 128 <= len <= 255

        data_pattern_bins:
            "all_zeros"     - every byte == 0x00
            "all_ones"      - every byte == 0xFF
            "mixed"         - all other patterns

    MISS bins are flagged in report_phase for CI grep.
    """

    _LEN_BINS: list[tuple[str, int, int]] = [
        ("single_byte", 1, 1),
        ("short_2_7", 2, 7),
        ("medium_8_63", 8, 63),
        ("long_64_127", 64, 127),
        ("max_128_255", 128, 255),
    ]

    def build_phase(self) -> None:
        self._fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.analysis_export = self._fifo.analysis_export

        self.payload_len_bins: dict[str, int] = {label: 0 for label, *_ in self._LEN_BINS}
        self.data_pattern_bins: dict[str, int] = {
            "all_zeros": 0,
            "all_ones": 0,
            "mixed": 0,
        }

    async def run_phase(self) -> None:
        # _reset_per_test_
        self.payload_len_bins = {label: 0 for label, *_ in self._LEN_BINS}
        self.data_pattern_bins = {"all_zeros": 0, "all_ones": 0, "mixed": 0}
        while True:
            txn: AxisTransaction = await self._fifo.get()
            self._sample(txn)

    def _sample(self, txn: AxisTransaction) -> None:
        length = len(txn.data)
        for label, lo, hi in self._LEN_BINS:
            if lo <= length <= hi:
                self.payload_len_bins[label] += 1
                break

        if all(b == 0x00 for b in txn.data):
            self.data_pattern_bins["all_zeros"] += 1
        elif all(b == 0xFF for b in txn.data):
            self.data_pattern_bins["all_ones"] += 1
        else:
            self.data_pattern_bins["mixed"] += 1

    def report_phase(self) -> None:
        self.logger.info("=== CRC Coverage Report ===")
        self.logger.info("  Payload length bins:")
        for label, count in self.payload_len_bins.items():
            status = "HIT " if count else "MISS"
            self.logger.info(f"    {label:<20s} {status}  ({count})")
        self.logger.info("  Data pattern bins:")
        for label, count in self.data_pattern_bins.items():
            status = "HIT " if count else "MISS"
            self.logger.info(f"    {label:<20s} {status}  ({count})")
