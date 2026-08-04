# verif/cp_inserter/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.cp_inserter.seq_item import CpInserterSeqItem


class RandomSingleSymbolSeq(uvm_sequence):
    """One symbol of n_fft random samples at a fixed cp_len."""

    def __init__(self, name: str = "RandomSingleSymbolSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 9
        self.samp_w: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        item = CpInserterSeqItem()
        item.samples = [random.randint(0, mask) for _ in range(self.n_fft)]
        item.cp_len = self.cp_len
        item.samp_w = self.samp_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiSymbolSeq(uvm_sequence):
    """
    count back-to-back symbols, each with n_fft random samples at a fixed cp_len.

    Primary regression for inter-symbol contamination: no sample from symbol N
    may appear in the CP or payload region of symbol N+1.
    """

    def __init__(self, name: str = "MultiSymbolSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 9
        self.samp_w: int = 16
        self.count: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        for _ in range(self.count):
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(self.n_fft)]
            item.cp_len = self.cp_len
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)


class CountingPatternSeq(uvm_sequence):
    """
    One symbol where samples[i] = i & mask.

    The CP copy is trivially verifiable by inspection: output[0..cp_len-1]
    must equal [n_fft-cp_len, .., n_fft-1] (mod mask).
    """

    def __init__(self, name: str = "CountingPatternSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 9
        self.samp_w: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        item = CpInserterSeqItem()
        item.samples = [i & mask for i in range(self.n_fft)]
        item.cp_len = self.cp_len
        item.samp_w = self.samp_w
        await self.start_item(item)
        await self.finish_item(item)


class VaryingCpLenSeq(uvm_sequence):
    """
    One symbol per cp_len value in cp_lens, driven back-to-back.

    Models the 5G NR slot structure: symbol 0 uses the extended CP, symbols
    1-13 use the normal CP. Exercises runtime cp_len reconfiguration between
    consecutive packets.
    """

    def __init__(self, name: str = "VaryingCpLenSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.samp_w: int = 16
        self.cp_lens: list[int] = [0, 4, 8, 16]

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        for cp_len in self.cp_lens:
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(self.n_fft)]
            item.cp_len = cp_len
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)


class ZeroCpSeq(uvm_sequence):
    """
    count symbols with cp_len=0 - pure passthrough.

    Output must equal input verbatim. Verifies the DUT drives tlast at
    beat n_fft-1 without prepending any samples.
    """

    def __init__(self, name: str = "ZeroCpSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.samp_w: int = 16
        self.count: int = 8

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        for _ in range(self.count):
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(self.n_fft)]
            item.cp_len = 0
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)
