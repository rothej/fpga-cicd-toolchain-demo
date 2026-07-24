# verif/qam_demapper/env.py

from pyuvm import uvm_env

from verif.qam_demapper.agent import QamDemapperAgent
from verif.qam_demapper.coverage import QamDemapperCoverageCollector
from verif.qam_demapper.monitors import QamDemapperOutputMonitor
from verif.qam_demapper.scoreboard import QamDemapperScoreboard


class QamDemapperEnv(uvm_env):
    """
    Environment for qam_demapper.sv.

    Analysis connectivity:
        tx_agent.driver.ap ──┬──> scoreboard.tx_export
                             └──> coverage.tx_export
        rx_mon.ap          ──┬──> scoreboard.rx_export
                             └──> coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = QamDemapperAgent.create("tx_agent", self)
        self.rx_mon = QamDemapperOutputMonitor.create("rx_mon", self)
        self.scoreboard = QamDemapperScoreboard.create("scoreboard", self)
        self.coverage = QamDemapperCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
