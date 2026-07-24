# verif/qam_mapper/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.qam_mapper.driver import QamMapperDriver


class QamMapperAgent(uvm_agent):
    """TX-only agent for qam_mapper.sv input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = QamMapperDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
