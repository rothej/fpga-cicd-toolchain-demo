# verif/scrambler/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
from verif.scrambler.seq_item import ScramblerSeqItem

# Representative 31-bit cinit values.
# Derived from TS 38.211 S6.3.1.1: cinit = N_ID * 2^10 + n_RNTI (mod 2^31)
_TEST_CINIT_VALUES: list[int] = [
    0x00000000,  # degenerate: x2 all zeros -> c(n) = x1(n)
    0x00000001,
    0x12345678 & 0x7FFFFFFF,
    0x5A5A5A5A & 0x7FFFFFFF,
    0x7FFFFFFF,  # x2 all ones
]


class RandomDataSeq(uvm_sequence):
    """
    *count* packets of random data, fixed cinit from ConfigDB.

    ConfigDB keys: cinit, data_w, min_len, max_len, count
    """

    async def body(self) -> None:
        cinit = _cfg(self, "cinit", 0x12345678 & 0x7FFFFFFF)
        data_w = _cfg(self, "data_w", 8)
        min_len = _cfg(self, "min_len", 8)
        max_len = _cfg(self, "max_len", 256)
        count = _cfg(self, "count", 32)
        mask = (1 << data_w) - 1

        for _ in range(count):
            item = ScramblerSeqItem()
            item.cinit = cinit
            item.data_w = data_w
            item.data = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            await self.start_item(item)
            await self.finish_item(item)


class AllZerosSeq(uvm_sequence):
    """
    All-zero input packets.

    Because scramble(0, cinit) == Gold-sequence, the DUT output must
    exactly equal the Gold sequence - a direct check of the LFSR logic.

    ConfigDB keys: cinit, data_w, length, count
    """

    async def body(self) -> None:
        cinit = _cfg(self, "cinit", 0x12345678 & 0x7FFFFFFF)
        data_w = _cfg(self, "data_w", 8)
        length = _cfg(self, "length", 256)
        count = _cfg(self, "count", 4)

        for _ in range(count):
            item = ScramblerSeqItem()
            item.cinit = cinit
            item.data_w = data_w
            item.data = [0] * length
            await self.start_item(item)
            await self.finish_item(item)


class MultiCinitSeq(uvm_sequence):
    """
    One packet per entry in _TEST_CINIT_VALUES.

    Verifies that the DUT correctly re-initialises the Gold sequence for
    each new cinit - covers different cell-ID / RNTI combinations.

    ConfigDB keys: data_w, min_len, max_len
    """

    async def body(self) -> None:
        data_w = _cfg(self, "data_w", 8)
        min_len = _cfg(self, "min_len", 16)
        max_len = _cfg(self, "max_len", 128)
        mask = (1 << data_w) - 1

        for cinit in _TEST_CINIT_VALUES:
            item = ScramblerSeqItem()
            item.cinit = cinit
            item.data_w = data_w
            item.data = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            await self.start_item(item)
            await self.finish_item(item)
