# verif/cp_remover/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class CpRemoverSeqItem(uvm_sequence_item):
    """
    Sequence item for cp_remover.sv.

    full_samples - flat list of (cp_len + N_FFT) integer sample words;
                   full_samples[0 : cp_len] -> CP region (discarded by DUT)
                   full_samples[cp_len :]   -> payload   (emitted by DUT)
    cp_len       - cyclic prefix length in samples; driven on cp_len sideband
    samp_w       - SAMP_W RTL parameter; determines tdata mask width
    """

    def __init__(self, name: str = "cp_remover_seq_item") -> None:
        super().__init__(name)
        self.full_samples: list[int] = []
        self.cp_len: int = 0
        self.samp_w: int = 16

    @property
    def n_fft(self) -> int:
        return len(self.full_samples) - self.cp_len

    def __str__(self) -> str:
        return (
            f"CpRemoverSeqItem("
            f"pkt_len={len(self.full_samples)}, "
            f"cp_len={self.cp_len}, "
            f"n_fft={self.n_fft})"
        )
