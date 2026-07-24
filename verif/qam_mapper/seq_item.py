# verif/qam_mapper/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class QamMapperSeqItem(uvm_sequence_item):
    """
    Sequence item for qam_mapper.sv.

    data      - input words; mod_order LSBs per word represent one symbol
    mod_order - modulation order: 2=QPSK, 4=16-QAM, 6=64-QAM, 8=256-QAM
    data_w    - DATA_W RTL parameter (≥ mod_order); upper bits are zero-padded
    """

    _MO_NAMES = {2: "QPSK", 4: "16-QAM", 6: "64-QAM", 8: "256-QAM"}

    def __init__(self, name: str = "qam_mapper_seq_item") -> None:
        super().__init__(name)
        self.data: list[int] = []
        self.mod_order: int = 2
        self.data_w: int = 8

    def __str__(self) -> str:
        mo_str = self._MO_NAMES.get(self.mod_order, f"MO{self.mod_order}")
        return f"QamMapperSeqItem(mod={mo_str}, len={len(self.data)}, data_w={self.data_w})"
