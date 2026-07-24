# verif/nr_chain/virtual_sequencer.py

from __future__ import annotations

from pyuvm import uvm_sequencer


class NrChainVirtualSequencer(uvm_sequencer):
    """
    Virtual sequencer for the nr_chain loopback testbench.

    tx_sequencer is populated during NrChainEnv.connect_phase:
        self.vseqr.tx_sequencer = self.tx_agent.sequencer

    Virtual sequences access it as:
        self.sequencer.tx_sequencer
    """

    def __init__(self, name: str, parent) -> None:
        super().__init__(name, parent)
        self.tx_sequencer = None  # set by NrChainEnv.connect_phase
