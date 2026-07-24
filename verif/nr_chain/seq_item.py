# verif/nr_chain/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class NrChainSeqItem(uvm_sequence_item):
    """
    Transport block for the nr_chain loopback testbench.

    payload        - raw data bytes driven into nr_tx_chain before CRC
                     attachment; the TX chain appends POLY_W/8 CRC bytes
                     internally before scrambling and modulation
    cp_len         - cyclic prefix length in samples; presented on the cp_len
                     sideband and must match between TX insert and RX remove
    scrambler_seed - 32-bit LFSR seed; shared between TX scrambler and RX
                     descrambler - mismatch produces a CRC failure, not a
                     misalignment failure
    data_w         - DATA_W RTL parameter; determines tdata byte width mask
    """

    def __init__(self, name: str = "nr_chain_seq_item") -> None:
        super().__init__(name)
        self.payload: list[int] = []
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8

    def __str__(self) -> str:
        return (
            f"NrChainSeqItem("
            f"payload_len={len(self.payload)}, "
            f"cp_len={self.cp_len}, "
            f"seed=0x{self.scrambler_seed:08x})"
        )
