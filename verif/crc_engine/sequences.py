# verif/crc_engine/sequences.py

"""
verif/crc_engine/sequences.py

Sequences for the crc_engine testbench.
"""

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.axis_agent import AxisTransaction

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
    Send count random payloads of length in [min_len, max_len].

    Set seed to an integer for reproducible runs; None uses the current
    system time (non-deterministic but still functionally correct).
    """

    def __init__(self, name: str = "CrcRandomSeq") -> None:
        super().__init__(name)
        self.count: int = 64
        self.min_len: int = 1
        self.max_len: int = 128
        self.seed: int | None = None

    async def body(self) -> None:
        if self.seed is not None:
            random.seed(self.seed)

        for _ in range(self.count):
            txn = AxisTransaction()
            txn.data = [
                random.randint(0, 255) for _ in range(random.randint(self.min_len, self.max_len))
            ]
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
