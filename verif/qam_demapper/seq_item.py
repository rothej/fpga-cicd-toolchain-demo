# verif/qam_demapper/seq_item.py

from __future__ import annotations

from pyuvm import uvm_sequence_item


class QamDemapperSeqItem(uvm_sequence_item):
    """
    Sequence item for qam_demapper.sv.

    symbols   - list of (I, Q) unnormalized integer pairs to drive on s_axis
    mod_order - modulation order: 2=QPSK, 4=16-QAM, 6=64-QAM, 8=256-QAM
    iq_w      - IQ_W RTL parameter; determines tdata packing width per component
    """

    _MO_NAMES = {2: "QPSK", 4: "16-QAM", 6: "64-QAM", 8: "256-QAM"}

    def __init__(self, name: str = "qam_demapper_seq_item") -> None:
        super().__init__(name)
        self.symbols: list[tuple[int, int]] = []
        self.mod_order: int = 2
        self.iq_w: int = 8

    def __str__(self) -> str:
        mo_str = self._MO_NAMES.get(self.mod_order, f"MO{self.mod_order}")
        return f"QamDemapperSeqItem(mod={mo_str}, n_symbols={len(self.symbols)}, iq_w={self.iq_w})"
