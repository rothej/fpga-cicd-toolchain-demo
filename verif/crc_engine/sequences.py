# verif/crc_engine/sequences.py

"""
verif/crc_engine/sequences.py

Sequences for the crc_engine testbench.
"""

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.axis_agent import AxisTransaction
from verif.common.config_utils import _cfg

__all__ = [
    "CrcKnownVectorSeq",
    "CrcRandomSeq",
    "CrcEdgeCaseSeq",
]

_KNOWN_PAYLOADS: list[list[int]] = [
    [0x00],
    [0xFF],
    [0x31, 0x32, 0x33],
    list(range(16)),
    list(range(256)),
]


class CrcKnownVectorSeq(uvm_sequence):
    """Send each entry in _KNOWN_PAYLOADS as one AxisTransaction."""

    async def body(self) -> None:
        for payload in _KNOWN_PAYLOADS:
            txn = AxisTransaction()
            txn.data = list(payload)
            txn.last = True
            await self.start_item(txn)
            await self.finish_item(txn)


class CrcRandomSeq(uvm_sequence):
    """
    Send *rand_count* random payloads of length in [rand_min_len, rand_max_len].

    ConfigDB keys: rand_count, rand_min_len, rand_max_len, rand_seed
    """

    async def body(self) -> None:
        count = int(_cfg(self, "rand_count", 64))
        min_len = int(_cfg(self, "rand_min_len", 1))
        max_len = int(_cfg(self, "rand_max_len", 128))

        seed = _cfg(self, "rand_seed", None)
        if seed is not None:
            random.seed(int(seed))

        for _ in range(count):
            txn = AxisTransaction()
            txn.data = [random.randint(0, 255) for _ in range(random.randint(min_len, max_len))]
            txn.last = True
            await self.start_item(txn)
            await self.finish_item(txn)


class CrcEdgeCaseSeq(uvm_sequence):
    """
    Corner-case payloads that stress LFSR boundary conditions.

    Payloads: single 0x00, single 0xFF, [0x00,0xFF],
              255x 0x00, 255x 0xFF.
    """

    _EDGE_PAYLOADS: list[list[int]] = [
        [0x00],
        [0xFF],
        [0x00, 0xFF],
        [0x00] * 255,
        [0xFF] * 255,
    ]

    async def body(self) -> None:
        for payload in self._EDGE_PAYLOADS:
            txn = AxisTransaction()
            txn.data = list(payload)
            txn.last = True
            await self.start_item(txn)
            await self.finish_item(txn)
