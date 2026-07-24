# verif/qam_mapper/env.py

from pyuvm import uvm_env

from verif.qam_mapper.agent import QamMapperAgent
from verif.qam_mapper.coverage import QamMapperCoverageCollector
from verif.qam_mapper.monitors import QamMapperOutputMonitor
from verif.qam_mapper.scoreboard import QamMapperScoreboard


class QamMapperEnv(uvm_env):
    """
    Environment for qam_mapper.sv.

    Analysis connectivity:
        tx_agent.driver.ap ──┬──> scoreboard.tx_export
                             └──> coverage.tx_export
        rx_mon.ap          ──┬──> scoreboard.rx_export
                             └──> coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = QamMapperAgent.create("tx_agent", self)
        self.rx_mon = QamMapperOutputMonitor.create("rx_mon", self)
        self.scoreboard = QamMapperScoreboard.create("scoreboard", self)
        self.coverage = QamMapperCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
