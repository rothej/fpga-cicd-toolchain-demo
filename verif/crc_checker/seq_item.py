# verif/crc_checker/seq_item.py

"""
verif/crc_checker/seq_item.py

Sequence item for crc_checker.sv.

crc_checker.sv has a byte-serial, no-backpressure input interface
(data_in / data_valid / last / init) with crc_ref as a sideband port
driven coincident with the last data_valid beat.  The CRC is NOT appended
to the data stream — it is presented in parallel on the crc_ref port.
"""

from __future__ import annotations

from pyuvm import uvm_sequence_item

# crc_type_e encoding matches crc_pkg.sv:
#   CRC24A=0  CRC24B=1  CRC24C=2  CRC16=3  CRC11=4  CRC6=5
_CRCTYPE_PARAMS: dict[int, tuple[int, int]] = {
    0: (0x864CFB, 24),  # CRC24A
    1: (0x800063, 24),  # CRC24B
    2: (0xB2B117, 24),  # CRC24C
    3: (0x11021, 16),  # CRC16
    4: (0x000621, 11),  # CRC11
    5: (0x000021, 6),  # CRC6
}

_CRCTYPE_NAMES: dict[int, str] = {
    0: "CRC24A",
    1: "CRC24B",
    2: "CRC24C",
    3: "CRC16",
    4: "CRC11",
    5: "CRC6",
}


class CrcCheckerSeqItem(uvm_sequence_item):
    """
    Sequence item for crc_checker.sv.

    Fields set by the sequence before start_item / finish_item:
        payload   - data bytes driven on data_in / data_valid / last
        crc_type  - crc_type_e integer value (0-5); matches crc_pkg.sv encoding
        crc_word  - CRC value driven on the crc_ref sideband, coincident with last
        corrupt   - True if crc_word was intentionally flipped (expect crc_fail)

    Properties:
        poly      - generator polynomial derived from crc_type
        crc_width - CRC width in bits derived from crc_type

    Driver protocol:
        crc_ref is driven as a parallel sideband on the cycle where
        data_valid=1 AND last=1.  Sequences must compute crc_word via
        crc_compute() before calling finish_item().
    """

    def __init__(self, name: str = "crc_checker_seq_item") -> None:
        super().__init__(name)
        self.payload: list[int] = []
        self.crc_type: int = 0  # CRC24A
        self.crc_word: int = 0
        self.corrupt: bool = False

    # ------------------------------------------------------------------
    # Derived properties (read-only)
    # ------------------------------------------------------------------

    @property
    def poly(self) -> int:
        """Generator polynomial for the selected crc_type."""
        return _CRCTYPE_PARAMS[self.crc_type][0]

    @property
    def crc_width(self) -> int:
        """CRC register width in bits for the selected crc_type."""
        return _CRCTYPE_PARAMS[self.crc_type][1]

    def __str__(self) -> str:
        tag = "CORRUPT" if self.corrupt else "valid"
        name = _CRCTYPE_NAMES.get(self.crc_type, f"type{self.crc_type}")
        fmt = max(self.crc_width // 4, 1)
        return (
            f"CrcCheckerSeqItem({tag} {name} "
            f"len={len(self.payload)}B "
            f"crc=0x{self.crc_word:0{fmt}X})"
        )
