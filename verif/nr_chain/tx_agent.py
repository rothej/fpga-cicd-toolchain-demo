# verif/nr_chain/tx_agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.nr_chain.driver import NrChainDriver


class NrChainTxAgent(uvm_agent):
    """TX-only agent for nr_chain_top's byte-level input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = NrChainDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
