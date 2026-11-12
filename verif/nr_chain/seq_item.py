# verif/nr_chain/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class NrChainSeqItem(uvm_sequence_item):
    """
    Transport block for the nr_chain loopback testbench.

    payload        - raw data bytes driven into nr_tx_chain. Length must be a non-zero
                     multiple of N_FFT (enforced by NrChainDriver). Values must fit in
                     MOD_ORDER bits: nr_rx_chain masks its output to MOD_ORDER bits, so
                     wider values cannot round-trip.
    cp_len         - cyclic prefix length in samples; presented on the cp_len sideband
                     and shared by TX cp_inserter and RX cp_remover
    scrambler_seed - scrambler cinit; only bits [30:0] reach the DUT (bit 31 is ignored).
                     Shared by the TX scrambler and RX descrambler - a mismatch shows up
                     as payload corruption
    data_w         - DATA_W RTL parameter, recorded for reference. The driver masks with
                     its own ConfigDB "data_w", not this field.
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
