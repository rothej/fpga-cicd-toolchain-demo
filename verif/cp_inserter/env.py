# verif/cp_inserter/env.py

from pyuvm import uvm_env

from verif.cp_inserter.agent import CpInserterAgent
from verif.cp_inserter.coverage import CpInserterCoverageCollector
from verif.cp_inserter.monitors import CpInserterOutputMonitor
from verif.cp_inserter.scoreboard import CpInserterScoreboard


class CpInserterEnv(uvm_env):
    """
    Environment for cp_inserter.sv.

    Analysis connectivity:
        tx_agent.driver.ap ──┬──> scoreboard.tx_export
                             └──> coverage.tx_export
        rx_mon.ap          ──┬──> scoreboard.rx_export
                             └──> coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = CpInserterAgent.create("tx_agent", self)
        self.rx_mon = CpInserterOutputMonitor.create("rx_mon", self)
        self.scoreboard = CpInserterScoreboard.create("scoreboard", self)
        self.coverage = CpInserterCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
