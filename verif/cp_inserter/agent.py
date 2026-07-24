# verif/cp_inserter/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.cp_inserter.driver import CpInserterDriver


class CpInserterAgent(uvm_agent):
    """TX-only agent for cp_inserter.sv input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = CpInserterDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
