# verif/crc_checker/sequences.py

"""
verif/crc_checker/sequences.py

Sequences for crc_checker.sv.

Each sequence generates CrcCheckerSeqItems and pre-computes crc_word so
the driver can present it on the crc_ref sideband coincident with last.
The CRC is NOT appended to the data stream.
"""

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
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
    Generate *count* packets with correctly computed CRCs.

    Expected DUT response: crc_pass pulses for every packet.

    ConfigDB keys: crc_type, min_len, max_len, count
    """

    async def body(self) -> None:
        crc_type = _cfg(self, "crc_type", 0)  # CRC24A
        min_len = _cfg(self, "min_len", 1)
        max_len = _cfg(self, "max_len", 128)
        count = _cfg(self, "count", 32)

        for _ in range(count):
            item = _make_item(crc_type, min_len, max_len, corrupt=False)
            await self.start_item(item)
            await self.finish_item(item)


class CorruptCrcSeq(uvm_sequence):
    """
    Generate *count* packets where a single random CRC bit is flipped.

    Expected DUT response: crc_fail pulses for every packet.
    All crc_width bit positions are exercised across the run.

    ConfigDB keys: crc_type, min_len, max_len, count
    """

    async def body(self) -> None:
        crc_type = _cfg(self, "crc_type", 0)
        min_len = _cfg(self, "min_len", 1)
        max_len = _cfg(self, "max_len", 128)
        count = _cfg(self, "count", 32)

        for _ in range(count):
            item = _make_item(crc_type, min_len, max_len, corrupt=True)
            await self.start_item(item)
            await self.finish_item(item)


class RandomMixSeq(uvm_sequence):
    """
    Randomly interleave valid and corrupt packets.

    Exercises all four (corrupt, crc_ok) cross cells in a single run.

    Additional ConfigDB key:
        corrupt_ratio - float [0.0, 1.0], fraction of corrupt packets
                        (default 0.5)
    """

    async def body(self) -> None:
        crc_type = _cfg(self, "crc_type", 0)
        min_len = _cfg(self, "min_len", 1)
        max_len = _cfg(self, "max_len", 128)
        count = _cfg(self, "count", 64)
        corrupt_ratio = _cfg(self, "corrupt_ratio", 0.5)

        for _ in range(count):
            corrupt = random.random() < corrupt_ratio
            item = _make_item(crc_type, min_len, max_len, corrupt=corrupt)
            await self.start_item(item)
            await self.finish_item(item)
