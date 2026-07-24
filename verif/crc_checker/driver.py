# verif/crc_checker/driver.py

"""
verif/crc_checker/driver.py

Byte-serial driver for crc_checker.sv.

Port mapping:
    clk, rst_n   - clock and active-low reset
    init         - synchronous LFSR clear; asserted one idle cycle per packet
    crc_type     - crc_type_e value; stable for the duration of each packet
    data_in      - 8-bit input byte
    data_valid   - handshake: DUT accepts every cycle data_valid=1 (no tready)
    last         - asserted coincident with the final data_valid beat
    crc_ref      - 24-bit expected CRC sideband; valid coincident with last
"""

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_driver

from verif.crc_checker.seq_item import CrcCheckerSeqItem


class CrcCheckerDriver(uvm_driver):
    """
    Drives crc_checker.sv's byte-serial input interface.

    Per-packet protocol:
      1. Assert init=1 for one idle cycle (data_valid=0); set crc_type.
      2. Drive each payload byte on data_in/data_valid every clock cycle
         (no tready — crc_engine accepts every valid beat unconditionally).
      3. On the final byte: assert last=1 AND drive crc_ref=item.crc_word
         simultaneously on the same cycle.
      4. De-assert data_valid, last, and crc_ref on the following cycle.

    Publishes each CrcCheckerSeqItem to ap after the full packet is
    accepted so scoreboard ordering matches the DUT's crc_pass/crc_fail
    pulse ordering.
    """

    def build_phase(self) -> None:
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "dut")

    async def run_phase(self) -> None:
        dut = self.dut

        # Safe idle state
        dut.init.value = 0
        dut.crc_type.value = 0
        dut.data_in.value = 0
        dut.data_valid.value = 0
        dut.last.value = 0
        dut.crc_ref.value = 0

        while True:
            item: CrcCheckerSeqItem = await self.seq_item_port.get_next_item()
            await self._drive(item)
            self.seq_item_port.item_done()
            self.ap.write(item)  # publish after full packet accepted

    async def _drive(self, item: CrcCheckerSeqItem) -> None:
        """Drive one complete packet onto the DUT bus."""
        dut = self.dut

        # --- Setup / init cycle ---
        # Assert init for one clock with data_valid=0 to clear the LFSR,
        # and present crc_type so it is stable before the first data beat.
        dut.crc_type.value = item.crc_type
        dut.init.value = 1
        dut.data_valid.value = 0
        dut.last.value = 0
        dut.crc_ref.value = 0
        await RisingEdge(dut.clk)
        dut.init.value = 0

        # --- Data phase ---
        n = len(item.payload)
        for idx, byte in enumerate(item.payload):
            is_last = idx == n - 1

            dut.data_in.value = byte
            dut.data_valid.value = 1
            dut.last.value = int(is_last)

            # crc_ref must be stable on the cycle where data_valid=1 AND last=1
            # (crc_checker.sv samples crc_ref_r on that cycle).
            if is_last:
                dut.crc_ref.value = item.crc_word

            await RisingEdge(dut.clk)  # no tready: advance every cycle

        # --- Idle: de-assert after the last beat ---
        dut.data_valid.value = 0
        dut.last.value = 0
        dut.crc_ref.value = 0
