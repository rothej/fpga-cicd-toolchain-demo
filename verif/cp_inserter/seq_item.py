# verif/cp_inserter/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class CpInserterSeqItem(uvm_sequence_item):
    """
    Sequence item for cp_inserter.sv.

    samples - list of N_FFT integer sample words to drive on s_axis
    cp_len  - cyclic prefix length in samples; driven on the cp_len sideband port
    samp_w  - SAMP_W RTL parameter; determines tdata and mask width
    """

    def __init__(self, name: str = "cp_inserter_seq_item") -> None:
        super().__init__(name)
        self.samples: list[int] = []
        self.cp_len: int = 0
        self.samp_w: int = 16

    def __str__(self) -> str:
        n = len(self.samples)
        return f"CpInserterSeqItem(n_fft={n}, cp_len={self.cp_len}, out_len={n + self.cp_len})"
