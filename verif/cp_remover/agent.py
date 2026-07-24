# verif/cp_remover/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.cp_remover.driver import CpRemoverDriver


class CpRemoverAgent(uvm_agent):
    """TX-only agent for cp_remover.sv input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = CpRemoverDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
