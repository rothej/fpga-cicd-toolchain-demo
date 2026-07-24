# verif/crc_checker/env.py

from pyuvm import uvm_env

from verif.crc_checker.agent import CrcCheckerAgent
from verif.crc_checker.coverage import CrcCoverageCollector
from verif.crc_checker.monitors import CrcStatusMonitor
from verif.crc_checker.scoreboard import CrcCheckerScoreboard


class CrcCheckerEnv(uvm_env):
    """
    Environment for crc_checker.sv.

    Analysis connectivity:
        tx_agent.driver.ap  ──┬──>  scoreboard.tx_export
                              └──>  coverage.tx_export

        rx_mon.ap           ──┬──>  scoreboard.rx_export
                              └──>  coverage.rx_export
    """

    def build_phase(self) -> None:
        self.tx_agent = CrcCheckerAgent.create("tx_agent", self)
        self.rx_mon = CrcStatusMonitor.create("rx_mon", self)
        self.scoreboard = CrcCheckerScoreboard.create("scoreboard", self)
        self.coverage = CrcCoverageCollector.create("coverage", self)

    def connect_phase(self) -> None:
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.rx_mon.ap.connect(self.scoreboard.rx_export)

        self.tx_agent.driver.ap.connect(self.coverage.tx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)
