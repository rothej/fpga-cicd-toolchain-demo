# verif/crc_checker/sequences.py

"""
verif/crc_checker/sequences.py

Sequences for crc_checker.sv.
"""

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.nr_ref_model import crc_compute
from verif.crc_checker.seq_item import _CRCTYPE_PARAMS, CrcCheckerSeqItem


def _make_item(
    crc_type: int,
    min_len: int,
    max_len: int,
    corrupt: bool,
    flip_bit: int | None = None,
) -> CrcCheckerSeqItem:
    """
    Build a populated CrcCheckerSeqItem.

    Generates a random payload of random length in [min_len, max_len],
    computes the correct CRC, then optionally flips one bit to corrupt it.
    """
    poly, width = _CRCTYPE_PARAMS[crc_type]
    item = CrcCheckerSeqItem()
    item.crc_type = crc_type
    item.payload = [random.randint(0, 255) for _ in range(random.randint(min_len, max_len))]
    good_crc = crc_compute(item.payload, poly, width)

    if corrupt:
        bit = flip_bit if flip_bit is not None else (1 << random.randint(0, width - 1))
        item.crc_word = good_crc ^ bit
    else:
        item.crc_word = good_crc

    item.corrupt = corrupt
    return item


class ValidCrcSeq(uvm_sequence):
    """
    Generate count packets with correctly computed CRCs.

    Expected DUT response: crc_pass pulses for every packet.
    """

    def __init__(self, name: str = "ValidCrcSeq") -> None:
        super().__init__(name)
        self.crc_type: int = 0  # CRC24A
        self.min_len: int = 1
        self.max_len: int = 128
        self.count: int = 32

    async def body(self) -> None:
        for _ in range(self.count):
            item = _make_item(self.crc_type, self.min_len, self.max_len, corrupt=False)
            await self.start_item(item)
            await self.finish_item(item)


class CorruptCrcSeq(uvm_sequence):
    """
    Generate count packets where a single random CRC bit is flipped.

    Expected DUT response: crc_fail pulses for every packet.
    All crc_width bit positions are exercised across the run.
    """

    def __init__(self, name: str = "CorruptCrcSeq") -> None:
        super().__init__(name)
        self.crc_type: int = 0  # CRC24A
        self.min_len: int = 1
        self.max_len: int = 128
        self.count: int = 32

    async def body(self) -> None:
        for _ in range(self.count):
            item = _make_item(self.crc_type, self.min_len, self.max_len, corrupt=True)
            await self.start_item(item)
            await self.finish_item(item)


class RandomMixSeq(uvm_sequence):
    """
    Randomly interleave valid and corrupt packets.

    Exercises all four (corrupt, crc_ok) cross cells in a single run.
    corrupt_ratio is the fraction of corrupt packets in [0.0, 1.0].
    """

    def __init__(self, name: str = "RandomMixSeq") -> None:
        super().__init__(name)
        self.crc_type: int = 0  # CRC24A
        self.min_len: int = 1
        self.max_len: int = 128
        self.count: int = 64
        self.corrupt_ratio: float = 0.5

    async def body(self) -> None:
        for _ in range(self.count):
            corrupt = random.random() < self.corrupt_ratio
            item = _make_item(self.crc_type, self.min_len, self.max_len, corrupt=corrupt)
            await self.start_item(item)
            await self.finish_item(item)
