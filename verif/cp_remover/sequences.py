# verif/cp_remover/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.cp_remover.seq_item import CpRemoverSeqItem


class RandomSingleSymbolSeq(uvm_sequence):
    """
    One packet of (cp_len + n_fft) random samples at a fixed cp_len.
    """

    def __init__(self, name: str = "RandomSingleSymbolSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 9
        self.samp_w: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        item = CpRemoverSeqItem()
        item.full_samples = [random.randint(0, mask) for _ in range(self.cp_len + self.n_fft)]
        item.cp_len = self.cp_len
        item.samp_w = self.samp_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiSymbolSeq(uvm_sequence):
    """
    count back-to-back packets, each (cp_len + n_fft) random samples.

    Primary regression for inter-symbol contamination: no sample from the
    payload of packet N may appear in the output of packet N+1.
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
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(self.cp_len + self.n_fft)]
            item.cp_len = self.cp_len
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)


class CountingPatternSeq(uvm_sequence):
    """
    One packet where full_samples[i] = i & mask.

    CP region  -> [0, 1, .., cp_len-1]                   (discarded)
    Payload    -> [cp_len, cp_len+1, .., cp_len+n_fft-1] (expected output)

    The discard boundary is trivially verifiable on a waveform viewer:
    the first output beat must equal cp_len, not 0.
    """

    def __init__(self, name: str = "CountingPatternSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 9
        self.samp_w: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        item = CpRemoverSeqItem()
        item.full_samples = [i & mask for i in range(self.cp_len + self.n_fft)]
        item.cp_len = self.cp_len
        item.samp_w = self.samp_w
        await self.start_item(item)
        await self.finish_item(item)


class VaryingCpLenSeq(uvm_sequence):
    """
    One packet per cp_len value in cp_lens, driven back-to-back.

    Models the 5G NR slot structure on the receiver side: symbol 0 arrives
    with the extended CP, symbols 1-13 with the normal CP. Exercises runtime
    cp_len reconfiguration between consecutive received packets.
    """

    def __init__(self, name: str = "VaryingCpLenSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.samp_w: int = 16
        self.cp_lens: list[int] = [0, 4, 8, 16]

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        for cp_len in self.cp_lens:
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(cp_len + self.n_fft)]
            item.cp_len = cp_len
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)


class ZeroCpSeq(uvm_sequence):
    """
    count packets with cp_len=0 - pure passthrough.

    Output must equal input verbatim; DUT must assert output tlast at beat
    n_fft-1 without suppressing any input samples.
    """

    def __init__(self, name: str = "ZeroCpSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.samp_w: int = 16
        self.count: int = 8

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        for _ in range(self.count):
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(self.n_fft)]
            item.cp_len = 0
            item.samp_w = self.samp_w
            await self.start_item(item)
            await self.finish_item(item)


class MaxCpLenSeq(uvm_sequence):
    """
    Single packet with cp_len at its maximum value.

    Stresses the discard counter at full depth: the DUT must suppress exactly
    cp_len leading beats before emitting the first output sample.
    """

    def __init__(self, name: str = "MaxCpLenSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.cp_len: int = 16
        self.samp_w: int = 16

    async def body(self) -> None:
        mask = (1 << self.samp_w) - 1
        item = CpRemoverSeqItem()
        item.full_samples = [random.randint(0, mask) for _ in range(self.cp_len + self.n_fft)]
        item.cp_len = self.cp_len
        item.samp_w = self.samp_w
        await self.start_item(item)
        await self.finish_item(item)
