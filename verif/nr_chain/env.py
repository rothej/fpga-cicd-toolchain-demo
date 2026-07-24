# verif/nr_chain/env.py

from pyuvm import uvm_env

from verif.nr_chain.coverage import NrChainCoverageCollector
from verif.nr_chain.monitors import NrChainLoopbackMonitor, NrChainOutputMonitor
from verif.nr_chain.scoreboard import NrChainScoreboard
from verif.nr_chain.tx_agent import NrChainTxAgent
from verif.nr_chain.virtual_sequencer import NrChainVirtualSequencer


class NrChainEnv(uvm_env):
    """
    Integration environment for the nr_chain loopback testbench.

    Analysis connectivity:
        tx_agent.driver.ap  ──┬──> scoreboard.tx_export
                              └──> coverage.tx_export
        rx_mon.ap           ──┬──> scoreboard.rx_export
                              └──> coverage.rx_export
        lb_mon.ap           ─────> coverage.lb_export   (coverage only)
    """

    def build_phase(self) -> None:
        self.tx_agent = NrChainTxAgent.create("tx_agent", self)
        self.rx_mon = NrChainOutputMonitor.create("rx_mon", self)
        self.lb_mon = NrChainLoopbackMonitor.create("lb_mon", self)
        self.scoreboard = NrChainScoreboard.create("scoreboard", self)
        self.coverage = NrChainCoverageCollector.create("coverage", self)
        self.vseqr = NrChainVirtualSequencer.create("vseqr", self)

    def connect_phase(self) -> None:
        # TX analysis
        self.tx_agent.driver.ap.connect(self.scoreboard.tx_export)
        self.tx_agent.driver.ap.connect(self.coverage.tx_export)

        # RX output analysis
        self.rx_mon.ap.connect(self.scoreboard.rx_export)
        self.rx_mon.ap.connect(self.coverage.rx_export)

        # Loopback point analysis (coverage only)
        self.lb_mon.ap.connect(self.coverage.lb_export)

        # Wire virtual sequencer -> concrete TX sequencer
        self.vseqr.tx_sequencer = self.tx_agent.sequencer
