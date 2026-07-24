# verif/common/axis_agent.py

"""
verif/common/axis_agent.py

Reusable AXI4-Stream-style agent for pyuvm/cocotb testbenches.

Signal names are configurable via ConfigDB so the same agent drives both
byte-serial interfaces (e.g. crc_engine: data_in/data_valid/last) and
wider symbol buses (e.g. qam_mapper: tdata/tvalid/tlast).

Required ConfigDB key:
    "dut"        : cocotb SimHandle - top-level DUT handle

Optional ConfigDB keys (defaults in parentheses):
    "clk_sig"    : str  ("clk")     - clock signal name
    "data_sig"   : str  ("tdata")   - data bus signal name
    "valid_sig"  : str  ("tvalid")  - valid signal name
    "last_sig"   : str  ("tlast")   - end-of-burst signal name
    "ready_sig"  : str  ("tready")  - backpressure ready signal name
    "has_ready"  : bool (True)      - False for source-only interfaces
    "is_active"  : bool (True)      - False = monitor-only (RX-side) agent
"""

from __future__ import annotations

from cocotb.triggers import RisingEdge
from pyuvm import (
    ConfigDB,
    uvm_agent,
    uvm_analysis_port,
    uvm_component,
    uvm_driver,
    uvm_sequence_item,
    uvm_sequencer,
)

from verif.common.config_utils import _cfg

__all__ = [
    "AxisTransaction",
    "AxisSequencer",
    "AxisDriver",
    "AxisMonitor",
    "AxisAgent",
]


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class AxisTransaction(uvm_sequence_item):
    """
    One AXI4-Stream burst transaction.

    Attributes:
        data: Ordered list of integer-valued beats. For byte-serial DUTs
              each element is 0-255; for wider buses the range scales with
              the port width.
        last: True when the final beat was accompanied by tlast asserted.
    """

    def __init__(self, name: str = "AxisTransaction") -> None:
        super().__init__(name)
        self.data: list[int] = []
        self.last: bool = True

    def __repr__(self) -> str:
        return f"AxisTransaction(data={self.data!r}, last={self.last!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AxisTransaction):
            return NotImplemented
        return self.data == other.data and self.last == other.last


# ---------------------------------------------------------------------------
# Sequencer
# ---------------------------------------------------------------------------


class AxisSequencer(uvm_sequencer):
    """Standard pass-through sequencer, no customization required."""


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


class AxisDriver(uvm_driver):
    """
    Drives AXI4-Stream signals beat-by-beat from AxisTransaction items.

    When has_ready is True the driver holds each beat until tready is sampled
    high on a rising clock edge. When has_ready is False (source-only
    interfaces such as crc_engine) the beat advances every cycle.

    tvalid is de-asserted after the last beat of every transaction to model
    a realistic inter-transaction gap.
    """

    def start_of_simulation_phase(self) -> None:
        dut = ConfigDB().get(self, "", "dut")

        self._clk = getattr(dut, _cfg(self, "clk_sig", "clk"))
        self._data = getattr(dut, _cfg(self, "data_sig", "tdata"))
        self._valid = getattr(dut, _cfg(self, "valid_sig", "tvalid"))
        self._last = getattr(dut, _cfg(self, "last_sig", "tlast"))

        self.has_ready: bool = _cfg(self, "has_ready", True)
        self._ready = getattr(dut, _cfg(self, "ready_sig", "tready")) if self.has_ready else None

        # De-assert valid at startup so the DUT sees a clean idle bus.
        self._valid.value = 0
        self._last.value = 0

    async def run_phase(self) -> None:
        while True:
            txn: AxisTransaction = await self.seq_item_port.get_next_item()
            await self._drive(txn)
            self.seq_item_port.item_done()

    async def _drive(self, txn: AxisTransaction) -> None:
        """Present all beats of *txn* to the DUT, then de-assert valid."""
        n = len(txn.data)
        for idx, beat in enumerate(txn.data):
            is_last = (idx == n - 1) and txn.last

            self._data.value = beat
            self._valid.value = 1
            self._last.value = int(is_last)

            # Advance on rising edge; hold the beat while ready is low.
            while True:
                await RisingEdge(self._clk)
                if not self.has_ready or int(self._ready.value) == 1:  # type: ignore[union-attr]
                    break

        self._valid.value = 0
        self._last.value = 0


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class AxisMonitor(uvm_component):
    """
    Passively samples AXI4-Stream beats on rising clock edges.

    Accumulates beats from the first active handshake until tlast is
    observed, then writes the complete AxisTransaction to ap.
    """

    def build_phase(self) -> None:
        self.ap: uvm_analysis_port = uvm_analysis_port("ap", self)

    def start_of_simulation_phase(self) -> None:
        dut = ConfigDB().get(self, "", "dut")

        self._clk = getattr(dut, _cfg(self, "clk_sig", "clk"))
        self._data = getattr(dut, _cfg(self, "data_sig", "tdata"))
        self._valid = getattr(dut, _cfg(self, "valid_sig", "tvalid"))
        self._last = getattr(dut, _cfg(self, "last_sig", "tlast"))

        self.has_ready: bool = _cfg(self, "has_ready", True)
        self._ready = getattr(dut, _cfg(self, "ready_sig", "tready")) if self.has_ready else None

    def _beat_active(self) -> bool:
        """True when a valid handshake is present on the current clock edge."""
        valid = int(self._valid.value) == 1
        ready = (int(self._ready.value) == 1) if self.has_ready else True  # type: ignore[union-attr]
        return valid and ready

    async def _wait_for_beat(self) -> None:
        """Advance to the next rising edge on which a beat is active."""
        await RisingEdge(self._clk)
        while not self._beat_active():
            await RisingEdge(self._clk)

    async def run_phase(self) -> None:
        while True:
            # Wait for the first active beat of a new transaction.
            await self._wait_for_beat()

            beats: list[int] = []
            last = False

            while not last:
                beats.append(int(self._data.value))
                last = int(self._last.value) == 1
                if not last:
                    # Advance to the next active beat; idle cycles are skipped.
                    await self._wait_for_beat()

            txn = AxisTransaction()
            txn.data = beats
            txn.last = True
            self.ap.write(txn)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AxisAgent(uvm_agent):
    """
    Bundles sequencer, driver, and monitor into one AXI4-Stream agent.

    When is_active=True (default) the agent can inject stimulus via its
    sequencer.  Set is_active=False for receive-only paths where only the
    monitor is needed.

    The analysis port is always reachable via agent.monitor.ap or the
    convenience property agent.ap.
    """

    def build_phase(self) -> None:
        self.is_active: bool = _cfg(self, "is_active", True)
        self.monitor = AxisMonitor("monitor", self)

        if self.is_active:
            self.sequencer = AxisSequencer("sequencer", self)
            self.driver = AxisDriver("driver", self)

    def connect_phase(self) -> None:
        if self.is_active:
            self.driver.seq_item_port.connect(self.sequencer.seq_item_export)

    @property
    def ap(self) -> uvm_analysis_port:
        """Convenience shortcut: env code can use agent.ap instead of agent.monitor.ap."""
        return self.monitor.ap
