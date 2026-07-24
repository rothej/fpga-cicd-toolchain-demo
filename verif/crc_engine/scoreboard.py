# verif/crc_engine/scoreboard.py

"""
verif/crc_engine/scoreboard.py

Scoreboard for crc_engine.sv.

TX FIFO: AxisTransaction       from tx_agent.ap  (payload bytes driven)
RX FIFO: CrcResultTransaction  from CrcOutputMonitor.ap  (crc_out captured)

Reference: crc_compute(tx.data, crc_poly, crc_width) must equal rx.crc_value.
"""

from __future__ import annotations

from pyuvm import uvm_scoreboard, uvm_tlm_analysis_fifo

from verif.common.axis_agent import AxisTransaction
from verif.common.config_utils import _cfg
from verif.common.nr_ref_model import CrcPoly, crc_compute
from verif.crc_engine.monitors import CrcResultTransaction

__all__ = ["CrcScoreboard"]


class CrcScoreboard(uvm_scoreboard):
    """
    Compares the DUT CRC output against the crc_compute() reference model.

    ConfigDB keys (set by the test):
        "crc_poly"  : int | CrcPoly  (CrcPoly.CRC24A) - polynomial
        "crc_width" : int            (24)              - CRC width in bits
    """

    def build_phase(self) -> None:
        self.payload_fifo = uvm_tlm_analysis_fifo("payload_fifo", self)
        self.result_fifo = uvm_tlm_analysis_fifo("result_fifo", self)
        self.pass_count: int = 0
        self.fail_count: int = 0

    async def run_phase(self) -> None:
        # _reset_per_test_
        self.pass_count = 0
        self.fail_count = 0
        poly = _cfg(self, "crc_poly", CrcPoly.CRC24A)
        width = int(_cfg(self, "crc_width", 24))

        while True:
            payload_txn: AxisTransaction = await self.payload_fifo.get()
            result_txn: CrcResultTransaction = await self.result_fifo.get()

            expected = crc_compute(payload_txn.data, poly, width)
            actual = result_txn.crc_value

            if actual == expected:
                self.pass_count += 1
                self.logger.info(
                    f"PASS  len={len(payload_txn.data):4d}  "
                    f"expected=0x{expected:06X}  actual=0x{actual:06X}"
                )
            else:
                self.fail_count += 1
                self.logger.error(
                    f"FAIL  len={len(payload_txn.data):4d}  "
                    f"expected=0x{expected:06X}  actual=0x{actual:06X}"
                )

    def check_phase(self) -> None:
        total = self.pass_count + self.fail_count
        if self.fail_count:
            self.logger.critical(f"Scoreboard: {self.fail_count}/{total} transactions FAILED.")
            raise AssertionError(f"CRC scoreboard: {self.fail_count} transaction(s) failed.")
        self.logger.info(f"Scoreboard: all {self.pass_count} transactions passed.")
