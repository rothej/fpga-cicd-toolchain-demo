# verif/crc_checker/agent.py

from pyuvm import uvm_agent, uvm_sequencer

from verif.crc_checker.driver import CrcCheckerDriver


class CrcCheckerAgent(uvm_agent):
    """
    TX-only agent for crc_checker.sv.

    Scoreboard and coverage collectors connect to driver.ap, which publishes
    CrcCheckerSeqItems after each packet is fully driven onto the bus.
    """

    def build_phase(self) -> None:
        self.sequencer = uvm_sequencer.create("sequencer", self)
        self.driver = CrcCheckerDriver.create("driver", self)

    def connect_phase(self) -> None:
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
