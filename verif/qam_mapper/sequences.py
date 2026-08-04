# verif/qam_mapper/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.qam_mapper.seq_item import QamMapperSeqItem

_ALL_MOD_ORDERS: list[int] = [2, 4, 6, 8]  # QPSK -> 256-QAM


class RandomDataSeq(uvm_sequence):
    """count packets of random data at a fixed mod_order."""

    def __init__(self, name: str = "RandomDataSeq") -> None:
        super().__init__(name)
        self.mod_order: int = 2
        self.data_w: int = 8
        self.min_len: int = 8
        self.max_len: int = 256
        self.count: int = 32

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1
        for _ in range(self.count):
            item = QamMapperSeqItem()
            item.mod_order = self.mod_order
            item.data_w = self.data_w
            item.data = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            await self.start_item(item)
            await self.finish_item(item)


class AllModOrdersSeq(uvm_sequence):
    """
    One random-data packet for each of QPSK -> 16-QAM -> 64-QAM -> 256-QAM.

    Verifies that the DUT correctly reconfigures when mod_order changes
    between back-to-back packets.
    """

    def __init__(self, name: str = "AllModOrdersSeq") -> None:
        super().__init__(name)
        self.data_w: int = 8
        self.min_len: int = 16
        self.max_len: int = 128

    async def body(self) -> None:
        for mo in _ALL_MOD_ORDERS:
            mask = (1 << mo) - 1
            item = QamMapperSeqItem()
            item.mod_order = mo
            item.data_w = self.data_w
            item.data = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            await self.start_item(item)
            await self.finish_item(item)


class AllConstellationPointsSeq(uvm_sequence):
    """
    One word per valid bit pattern for a given mod_order, in shuffled order.

    Guarantees every constellation point is exercised exactly once.
    Practical for all four mod_order values: 4, 16, 64, and 256 words
    respectively - all fast in simulation.
    """

    def __init__(self, name: str = "AllConstellationPointsSeq") -> None:
        super().__init__(name)
        self.mod_order: int = 4
        self.data_w: int = 8

    async def body(self) -> None:
        all_words = list(range(1 << self.mod_order))
        random.shuffle(all_words)
        item = QamMapperSeqItem()
        item.mod_order = self.mod_order
        item.data_w = self.data_w
        item.data = all_words
        await self.start_item(item)
        await self.finish_item(item)
