# verif/cp_remover/env.py

from pyuvm import uvm_env

from verif.cp_remover.agent import CpRemoverAgent
from verif.cp_remover.coverage import CpRemoverCoverageCollector
from verif.cp_remover.monitors import CpRemoverOutputMonitor
from verif.cp_remover.scoreboard import CpRemoverScoreboard


class CpRemoverEnv(uvm_env):
    """
    Environment for cp_remover.sv.

    Analysis connectivity:
        tx_agent.driver.ap ──┬──> scoreboard.tx_export
                             └──> coverage.tx_export
        rx_mon.ap          ──┬──> scoreboard.rx_export
                             └──> coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = CpRemoverAgent.create("tx_agent", self)
        self.rx_mon = CpRemoverOutputMonitor.create("rx_mon", self)
        self.scoreboard = CpRemoverScoreboard.create("scoreboard", self)
        self.coverage = CpRemoverCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
