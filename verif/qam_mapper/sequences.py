# verif/qam_mapper/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
from verif.qam_mapper.seq_item import QamMapperSeqItem

_ALL_MOD_ORDERS: list[int] = [2, 4, 6, 8]  # QPSK -> 256-QAM


class RandomDataSeq(uvm_sequence):
    """
    N packets of random data at a fixed mod_order.

    ConfigDB keys: mod_order, data_w, min_len, max_len, count
    """

    async def body(self) -> None:
        mod_order = _cfg(self, "mod_order", 2)
        data_w = _cfg(self, "data_w", 8)
        min_len = _cfg(self, "min_len", 8)
        max_len = _cfg(self, "max_len", 256)
        count = _cfg(self, "count", 32)
        mask = (1 << mod_order) - 1  # upper bits zero-padded

        for _ in range(count):
            item = QamMapperSeqItem()
            item.mod_order = mod_order
            item.data_w = data_w
            item.data = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            await self.start_item(item)
            await self.finish_item(item)


class AllModOrdersSeq(uvm_sequence):
    """
    One random-data packet for each of QPSK -> 16-QAM -> 64-QAM -> 256-QAM.

    Verifies that the DUT correctly reconfigures when mod_order changes
    between back-to-back packets.

    ConfigDB keys: data_w, min_len, max_len
    """

    async def body(self) -> None:
        data_w = _cfg(self, "data_w", 8)
        min_len = _cfg(self, "min_len", 16)
        max_len = _cfg(self, "max_len", 128)

        for mo in _ALL_MOD_ORDERS:
            mask = (1 << mo) - 1
            item = QamMapperSeqItem()
            item.mod_order = mo
            item.data_w = data_w
            item.data = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            await self.start_item(item)
            await self.finish_item(item)


class AllConstellationPointsSeq(uvm_sequence):
    """
    One word per valid bit pattern for a given mod_order, in shuffled order.

    Guarantees every constellation point is exercised exactly once.
    Practical for all four mod_order values: 4, 16, 64, and 256 words
    respectively - all fast in simulation.

    ConfigDB keys: mod_order, data_w
    """

    async def body(self) -> None:
        mod_order = _cfg(self, "mod_order", 4)
        data_w = _cfg(self, "data_w", 8)

        all_words = list(range(1 << mod_order))
        random.shuffle(all_words)  # avoid systematic ordering artefacts

        item = QamMapperSeqItem()
        item.mod_order = mod_order
        item.data_w = data_w
        item.data = all_words
        await self.start_item(item)
        await self.finish_item(item)
