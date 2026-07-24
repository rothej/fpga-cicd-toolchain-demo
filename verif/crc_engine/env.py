# verif/crc_engine/env.py

"""
verif/crc_engine/env.py

Environment for the crc_engine testbench.

crc_engine.sv uses a byte-serial, no-backpressure input interface
(data_in / data_valid / last) that maps directly to AxisAgent via
ConfigDB port-name remapping - no custom driver required.

Component hierarchy:
    CrcEngineEnv
    ├── AxisAgent       "tx_agent"   (active - drives data_in/data_valid/last)
    ├── CrcOutputMonitor             (passive - samples crc_out/crc_valid)
    ├── CrcScoreboard
    └── CrcCoverageCollector

TLM connections:
    tx_agent.ap  -> scoreboard.payload_fifo.analysis_export
    tx_agent.ap  -> coverage.analysis_export
    out_mon.ap   -> scoreboard.result_fifo.analysis_export
"""

from __future__ import annotations

from pyuvm import ConfigDB, uvm_env

from verif.common.axis_agent import AxisAgent
from verif.crc_engine.coverage import CrcCoverageCollector
from verif.crc_engine.monitors import CrcOutputMonitor
from verif.crc_engine.scoreboard import CrcScoreboard

__all__ = ["CrcEngineEnv"]


class CrcEngineEnv(uvm_env):
    """
    Top-level environment for the crc_engine testbench.

    build_phase remaps AxisAgent's generic signal names to crc_engine.sv's
    byte-serial port names via ConfigDB before instantiation, so the generic
    agent drives the right signals without subclassing.

    has_ready=False: crc_engine accepts every data_valid beat unconditionally;
    the driver advances every cycle without checking a ready signal.
    """

    def build_phase(self) -> None:
        ConfigDB().set(self, "tx_agent.*", "data_sig", "data_in")
        ConfigDB().set(self, "tx_agent.*", "valid_sig", "data_valid")
        ConfigDB().set(self, "tx_agent.*", "last_sig", "last")
        ConfigDB().set(self, "tx_agent.*", "has_ready", False)
        ConfigDB().set(self, "tx_agent.*", "is_active", True)

        self.tx_agent = AxisAgent.create("tx_agent", self)
        self.out_mon = CrcOutputMonitor.create("out_mon", self)
        self.scoreboard = CrcScoreboard.create("scoreboard", self)
        self.coverage = CrcCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.ap.connect(self.scoreboard.payload_fifo.analysis_export)
        self.tx_agent.ap.connect(self.coverage.analysis_export)
        self.out_mon.ap.connect(self.scoreboard.result_fifo.analysis_export)
