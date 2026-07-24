# verif/scrambler/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class ScramblerSeqItem(uvm_sequence_item):
    """
    Sequence item for scrambler.sv.

    data   - DATA_W-wide words to scramble
    cinit  - 31-bit Gold sequence initialisation value (TS 38.211 S5.2.1)
    data_w - bits per AXI4-S word; must match RTL DATA_W parameter
    """

    def __init__(self, name: str = "scrambler_seq_item") -> None:
        super().__init__(name)
        self.data: list[int] = []
        self.cinit: int = 0
        self.data_w: int = 8

    def __str__(self) -> str:
        return (
            f"ScramblerSeqItem("
            f"len={len(self.data)}, "
            f"cinit=0x{self.cinit:08X}, "
            f"data_w={self.data_w})"
        )
