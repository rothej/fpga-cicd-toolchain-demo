# verif/scrambler/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

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
    """count packets of random data, fixed cinit."""

    def __init__(self, name: str = "RandomDataSeq") -> None:
        super().__init__(name)
        self.cinit: int = 0x12345678 & 0x7FFFFFFF
        self.data_w: int = 8
        self.min_len: int = 8
        self.max_len: int = 256
        self.count: int = 32

    async def body(self) -> None:
        mask = (1 << self.data_w) - 1
        for _ in range(self.count):
            item = ScramblerSeqItem()
            item.cinit = self.cinit
            item.data_w = self.data_w
            item.data = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            await self.start_item(item)
            await self.finish_item(item)


class AllZerosSeq(uvm_sequence):
    """
    All-zero input packets.

    Because scramble(0, cinit) == Gold-sequence, the DUT output must
    exactly equal the Gold sequence - a direct check of the LFSR logic.
    """

    def __init__(self, name: str = "AllZerosSeq") -> None:
        super().__init__(name)
        self.cinit: int = 0x12345678 & 0x7FFFFFFF
        self.data_w: int = 8
        self.length: int = 256
        self.count: int = 4

    async def body(self) -> None:
        for _ in range(self.count):
            item = ScramblerSeqItem()
            item.cinit = self.cinit
            item.data_w = self.data_w
            item.data = [0] * self.length
            await self.start_item(item)
            await self.finish_item(item)


class MultiCinitSeq(uvm_sequence):
    """
    One packet per entry in cinit_values.

    Verifies that the DUT correctly re-initialises the Gold sequence for
    each new cinit - covers different cell-ID / RNTI combinations.
    """

    def __init__(self, name: str = "MultiCinitSeq") -> None:
        super().__init__(name)
        self.cinit_values: list[int] = list(_TEST_CINIT_VALUES)
        self.data_w: int = 8
        self.min_len: int = 16
        self.max_len: int = 128

    async def body(self) -> None:
        mask = (1 << self.data_w) - 1
        for cinit in self.cinit_values:
            item = ScramblerSeqItem()
            item.cinit = cinit
            item.data_w = self.data_w
            item.data = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            await self.start_item(item)
            await self.finish_item(item)
