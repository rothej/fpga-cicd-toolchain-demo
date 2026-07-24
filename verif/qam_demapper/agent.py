# verif/qam_demapper/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.qam_demapper.driver import QamDemapperDriver


class QamDemapperAgent(uvm_agent):
    """TX-only agent for qam_demapper.sv input."""

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = QamDemapperDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
