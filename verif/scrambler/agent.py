# verif/scrambler/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.scrambler.driver import ScramblerDriver


class ScramblerAgent(uvm_agent):
    """TX-only agent for scrambler.sv input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = ScramblerDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
