# verif/scrambler/env.py

from pyuvm import uvm_env

from verif.scrambler.agent import ScramblerAgent
from verif.scrambler.coverage import ScramblerCoverageCollector
from verif.scrambler.monitors import ScramblerOutputMonitor
from verif.scrambler.scoreboard import ScramblerScoreboard


class ScramblerEnv(uvm_env):
    """
    Environment for scrambler.sv.

    Analysis connectivity:
        tx_agent.driver.ap ──┬──> scoreboard.tx_export
                             └──> coverage.tx_export
        rx_mon.ap          ──┬──> scoreboard.rx_export
                             └──> coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = ScramblerAgent.create("tx_agent", self)
        self.rx_mon = ScramblerOutputMonitor.create("rx_mon", self)
        self.scoreboard = ScramblerScoreboard.create("scoreboard", self)
        self.coverage = ScramblerCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
