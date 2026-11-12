# verif/nr_chain/scoreboard.py

from __future__ import annotations

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

from verif.common.config_utils import _cfg
from verif.nr_chain.monitors import NrChainLoopbackItem, NrChainOutputItem
from verif.nr_chain.seq_item import NrChainSeqItem


class NrChainScoreboard(uvm_component):
    """
    End-to-end scoreboard for the nr_chain loopback testbench.

    TX FIFO: NrChainSeqItem        from driver.ap       (original payload)
    RX FIFO: NrChainOutputItem     from output monitor  (recovered bytes)
    LB FIFO: NrChainLoopbackItem   from loopback monitor (OFDM samples + tuser)

    Per block, two independent checks:
      1. Payload: rx.data == tx.payload (length first, then first bad byte).
      2. Framing at the TX->RX boundary:
           - sample count == (payload_len / N_FFT) * (N_FFT + cp_len)
           - block-start tuser fires exactly once, at sample index cp_len
         These catch symbol-count and CP-length errors that a payload-only
         comparison can mask.

    ConfigDB keys: "n_fft" (default 64).
    """

    def build_phase(self) -> None:
        self.tx_fifo = uvm_tlm_analysis_fifo("tx_fifo", self)
        self.rx_fifo = uvm_tlm_analysis_fifo("rx_fifo", self)
        self.lb_fifo = uvm_tlm_analysis_fifo("lb_fifo", self)
        self.tx_export = self.tx_fifo.analysis_export
        self.rx_export = self.rx_fifo.analysis_export
        self.lb_export = self.lb_fifo.analysis_export
        self.n_fft: int = _cfg(self, "n_fft", 64)
        self._passed = 0
        self._failed = 0

    async def run_phase(self) -> None:
        # _reset_per_test_
        self._passed = 0
        self._failed = 0
        while True:
            tx: NrChainSeqItem = await self.tx_fifo.get()
            rx: NrChainOutputItem = await self.rx_fifo.get()
            lb: NrChainLoopbackItem = await self.lb_fifo.get()

            errors = self._check_payload(tx, rx) + self._check_framing(tx, lb)
            if errors:
                self._failed += 1
                for msg in errors:
                    self.logger.error(f"{tx}: {msg}")
            else:
                self._passed += 1
                self.logger.debug(f"PASS {tx}")

    def _check_payload(self, tx: NrChainSeqItem, rx: NrChainOutputItem) -> list[str]:
        if len(rx.data) != len(tx.payload):
            delta = len(rx.data) - len(tx.payload)
            return [
                f"length mismatch: expected {len(tx.payload)} bytes, got {len(rx.data)} "
                f"({'extra' if delta > 0 else 'missing'} {abs(delta)})"
            ]
        errs = [
            (i, e, g) for i, (e, g) in enumerate(zip(tx.payload, rx.data, strict=True)) if e != g
        ]
        if errs:
            i0, e0, g0 = errs[0]
            return [f"{len(errs)} byte(s) wrong, first at byte[{i0}] exp=0x{e0:02x} got=0x{g0:02x}"]
        return []

    def _check_framing(self, tx: NrChainSeqItem, lb: NrChainLoopbackItem) -> list[str]:
        errors: list[str] = []
        exp_syms = len(tx.payload) // self.n_fft
        if lb.n_symbols(self.n_fft, tx.cp_len) != exp_syms:
            errors.append(
                f"loopback carried {len(lb.samples)} samples, expected {exp_syms} symbol(s) x "
                f"(N_FFT {self.n_fft} + cp_len {tx.cp_len}) = "
                f"{exp_syms * (self.n_fft + tx.cp_len)}"
            )
        if lb.user_idx != [tx.cp_len]:
            errors.append(
                f"block-start tuser at sample index {lb.user_idx}, expected exactly "
                f"[{tx.cp_len}] (first payload sample of the first symbol)"
            )
        return errors

    def check_phase(self) -> None:
        self.logger.info(f"Scoreboard: {self._passed} passed, {self._failed} failed")
        if self._passed + self._failed == 0:
            self.logger.critical("Scoreboard: no transactions checked")
            raise AssertionError("Scoreboard: no transactions were checked")
        if self._failed:
            self.logger.critical(f"{self._failed} scoreboard mismatch(es)")
            raise AssertionError(f"{self._failed} scoreboard mismatch(es)")
