# verif/nr_chain/coverage.py

from __future__ import annotations

import cocotb
from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.nr_chain.monitors import NrChainLoopbackItem, NrChainOutputItem
from verif.nr_chain.seq_item import NrChainSeqItem

_CP_BINS: list[tuple[str, int, int]] = [
    ("zero    [0]", 0, 1),
    ("short   [1,8)", 1, 8),
    ("medium  [8,32)", 8, 32),
    ("long    [32,+)", 32, 2**31),
]

_PL_BINS: list[tuple[str, int, int]] = [
    ("tiny   [1,8)", 1, 8),
    ("small  [8,64)", 8, 64),
    ("medium [64,256)", 64, 256),
    ("large  [256,+)", 256, 2**31),
]


def _bin(v: int, table: list[tuple[str, int, int]]) -> str:
    for label, lo, hi in table:
        if lo <= v < hi:
            return label
    return f"xlarge [{v})"


class NrChainCoverageCollector(uvm_component):
    """
    Functional coverage for the nr_chain loopback testbench.

    Dimensions:
        cp_len_bins      - four coarse CP length buckets (tx)
        payload_len_bins - four coarse payload size buckets (tx)
        seed_vals        - distinct scrambler seeds exercised
        crc_pass / fail  - CRC outcome counts
        lb_pkt_count     - total OFDM symbol packets observed at the loopback
                           point; _lb_pkt_count / _block_count ≈ OFDM symbols
                           per transport block (stable for fixed payload+MOD_ORDER)
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.lb_fifo = uvm_tlm_analysis_fifo("lb_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export
        self.lb_export = self.lb_fifo.analysis_export

        self._cp_bin_hits: dict[str, int] = {label: 0 for label, *_ in _CP_BINS}
        self._pl_bin_hits: dict[str, int] = {label: 0 for label, *_ in _PL_BINS}
        self._seed_vals: set[int] = set()
        self._crc_pass: int = 0
        self._crc_fail: int = 0
        self._lb_pkt_count: int = 0
        self._block_count: int = 0

    async def _consume_lb(self) -> None:
        """Background consumer: count OFDM packets at the loopback boundary."""
        while True:
            _: NrChainLoopbackItem = await self.lb_fifo.get()
            self._lb_pkt_count += 1

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._cp_bin_hits = {label: 0 for label, *_ in _CP_BINS}
        self._pl_bin_hits = {label: 0 for label, *_ in _PL_BINS}
        self._seed_vals = set()
        self._crc_pass = 0
        self._crc_fail = 0
        self._lb_pkt_count = 0
        self._block_count = 0
        cocotb.start_soon(self._consume_lb())

        while True:
            tx: NrChainSeqItem = await self.tx_fifo.get()
            rx: NrChainOutputItem = await self.rx_fifo.get()

            cp_label = _bin(tx.cp_len, _CP_BINS)
            pl_label = _bin(len(tx.payload), _PL_BINS)
            self._cp_bin_hits[cp_label] = self._cp_bin_hits.get(cp_label, 0) + 1
            self._pl_bin_hits[pl_label] = self._pl_bin_hits.get(pl_label, 0) + 1
            self._seed_vals.add(tx.scrambler_seed)
            if rx.crc_ok:
                self._crc_pass += 1
            else:
                self._crc_fail += 1
            self._block_count += 1

    def report_phase(self) -> None:
        self.logger.info("=== NR Chain Coverage Report ===")
        self.logger.info(f"  Transport blocks    : {self._block_count}")
        self.logger.info(f"  OFDM pkts at LB     : {self._lb_pkt_count}")
        if self._block_count:
            ratio = self._lb_pkt_count / self._block_count
            self.logger.info(f"  OFDM syms per block : {ratio:.2f}")
        self.logger.info(f"  CRC pass / fail     : {self._crc_pass} / {self._crc_fail}")
        self.logger.info(f"  Scrambler seeds     : {sorted(f'0x{s:06x}' for s in self._seed_vals)}")
        self.logger.info("  CP length distribution:")
        for label, count in self._cp_bin_hits.items():
            self.logger.info(f"    {label}: {count}")
        self.logger.info("  Payload size distribution:")
        for label, count in self._pl_bin_hits.items():
            self.logger.info(f"    {label}: {count}")

        if self._cp_bin_hits.get("zero    [0]", 0) == 0:
            self.logger.warning("  Coverage gap: cp_len=0 (no-CP passthrough) never exercised")
        if len(self._seed_vals) < 2:
            self.logger.warning(
                "  Coverage gap: only one scrambler seed exercised - "
                "add SeedSweepLoopbackTest to the regression"
            )
        if self._block_count and self._lb_pkt_count <= self._block_count:
            self.logger.warning(
                "  Coverage gap: no multi-symbol transport blocks exercised - "
                "every block used exactly one OFDM symbol (payload_len == N_FFT)"
            )
