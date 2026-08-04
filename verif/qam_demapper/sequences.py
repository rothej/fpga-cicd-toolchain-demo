# verif/qam_demapper/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.nr_ref_model import qam_map
from verif.qam_demapper.seq_item import QamDemapperSeqItem

_ALL_MOD_ORDERS: list[int] = [2, 4, 6, 8]


class RoundtripSeq(uvm_sequence):
    """
    count packets of random bit words at a fixed mod_order.

    Each word is mapped through qam_map to produce a valid (I, Q) pair.
    The scoreboard recovers the expected output via qam_demap - a full
    reference-model roundtrip independent of the DUT.
    """

    def __init__(self, name: str = "RoundtripSeq") -> None:
        super().__init__(name)
        self.mod_order: int = 2
        self.iq_w: int = 8
        self.min_len: int = 8
        self.max_len: int = 256
        self.count: int = 32

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1
        for _ in range(self.count):
            words = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            symbols = qam_map(words, self.mod_order)
            item = QamDemapperSeqItem()
            item.mod_order = self.mod_order
            item.iq_w = self.iq_w
            item.symbols = symbols
            await self.start_item(item)
            await self.finish_item(item)


class AllModOrdersRoundtripSeq(uvm_sequence):
    """
    One roundtrip packet for each of QPSK -> 16-QAM -> 64-QAM -> 256-QAM,
    sent back-to-back.

    Verifies that the DUT correctly reconfigures when mod_order changes
    between packets.
    """

    def __init__(self, name: str = "AllModOrdersRoundtripSeq") -> None:
        super().__init__(name)
        self.iq_w: int = 8
        self.min_len: int = 16
        self.max_len: int = 128

    async def body(self) -> None:
        for mo in _ALL_MOD_ORDERS:
            mask = (1 << mo) - 1
            words = [
                random.randint(0, mask) for _ in range(random.randint(self.min_len, self.max_len))
            ]
            symbols = qam_map(words, mo)
            item = QamDemapperSeqItem()
            item.mod_order = mo
            item.iq_w = self.iq_w
            item.symbols = symbols
            await self.start_item(item)
            await self.finish_item(item)


class AllConstellationPointsSeq(uvm_sequence):
    """
    All 2^mod_order valid (I, Q) constellation points in one shuffled packet.

    Guarantees full constellation input coverage in a single packet.
    """

    def __init__(self, name: str = "AllConstellationPointsSeq") -> None:
        super().__init__(name)
        self.mod_order: int = 4
        self.iq_w: int = 8

    async def body(self) -> None:
        all_words = list(range(1 << self.mod_order))
        random.shuffle(all_words)
        symbols = qam_map(all_words, self.mod_order)
        item = QamDemapperSeqItem()
        item.mod_order = self.mod_order
        item.iq_w = self.iq_w
        item.symbols = symbols
        await self.start_item(item)
        await self.finish_item(item)
