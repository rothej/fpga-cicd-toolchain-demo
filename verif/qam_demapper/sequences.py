# verif/qam_demapper/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
from verif.common.nr_ref_model import qam_map
from verif.qam_demapper.seq_item import QamDemapperSeqItem

_ALL_MOD_ORDERS: list[int] = [2, 4, 6, 8]


class RoundtripSeq(uvm_sequence):
    """
    N packets of random bit words at a fixed mod_order.

    Each word is mapped through the qam_map reference to produce a valid
    (I, Q) pair, which is stored in the seq_item and driven by the driver.
    The scoreboard recovers the expected output via qam_demap - a full
    reference-model roundtrip independent of the DUT.

    ConfigDB keys: mod_order, iq_w, min_len, max_len, count
    """

    async def body(self) -> None:
        mod_order = _cfg(self, "mod_order", 2)
        iq_w = _cfg(self, "iq_w", 8)
        min_len = _cfg(self, "min_len", 8)
        max_len = _cfg(self, "max_len", 256)
        count = _cfg(self, "count", 32)
        mask = (1 << mod_order) - 1

        for _ in range(count):
            words = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            symbols = qam_map(words, mod_order)

            item = QamDemapperSeqItem()
            item.mod_order = mod_order
            item.iq_w = iq_w
            item.symbols = symbols
            await self.start_item(item)
            await self.finish_item(item)


class AllModOrdersRoundtripSeq(uvm_sequence):
    """
    One roundtrip packet for each of QPSK -> 16-QAM -> 64-QAM -> 256-QAM,
    sent back-to-back.

    Verifies that the DUT correctly reconfigures when mod_order changes
    between packets - symmetric counterpart to AllModOrdersSeq in the mapper TB.

    ConfigDB keys: iq_w, min_len, max_len
    """

    async def body(self) -> None:
        iq_w = _cfg(self, "iq_w", 8)
        min_len = _cfg(self, "min_len", 16)
        max_len = _cfg(self, "max_len", 128)

        for mo in _ALL_MOD_ORDERS:
            mask = (1 << mo) - 1
            words = [random.randint(0, mask) for _ in range(random.randint(min_len, max_len))]
            symbols = qam_map(words, mo)

            item = QamDemapperSeqItem()
            item.mod_order = mo
            item.iq_w = iq_w
            item.symbols = symbols
            await self.start_item(item)
            await self.finish_item(item)


class AllConstellationPointsSeq(uvm_sequence):
    """
    All 2^mod_order valid (I, Q) constellation points in one shuffled packet.

    Enumerates every input bit word, maps through qam_map reference to
    produce the corresponding (I, Q) pair, then drives all of them.
    Guarantees full constellation input coverage in a single packet.

    ConfigDB keys: mod_order, iq_w
    """

    async def body(self) -> None:
        mod_order = _cfg(self, "mod_order", 4)
        iq_w = _cfg(self, "iq_w", 8)

        all_words = list(range(1 << mod_order))
        random.shuffle(all_words)
        symbols = qam_map(all_words, mod_order)

        item = QamDemapperSeqItem()
        item.mod_order = mod_order
        item.iq_w = iq_w
        item.symbols = symbols
        await self.start_item(item)
        await self.finish_item(item)
