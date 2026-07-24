# verif/cp_inserter/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
from verif.cp_inserter.seq_item import CpInserterSeqItem


class RandomSingleSymbolSeq(uvm_sequence):
    """
    One symbol of N_FFT random samples at a fixed cp_len.

    ConfigDB keys: n_fft, cp_len, samp_w
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        mask = (1 << samp_w) - 1

        item = CpInserterSeqItem()
        item.samples = [random.randint(0, mask) for _ in range(n_fft)]
        item.cp_len = cp_len
        item.samp_w = samp_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiSymbolSeq(uvm_sequence):
    """
    count back-to-back symbols, each with N_FFT random samples at a fixed cp_len.

    Primary regression for inter-symbol contamination: no sample from symbol N
    may appear in the CP or payload region of symbol N+1.

    ConfigDB keys: n_fft, cp_len, samp_w, count
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        count = _cfg(self, "count", 16)
        mask = (1 << samp_w) - 1

        for _ in range(count):
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(n_fft)]
            item.cp_len = cp_len
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)


class CountingPatternSeq(uvm_sequence):
    """
    One symbol where samples[i] = i & mask.

    The CP copy is trivially verifiable by inspection: output[0..cp_len-1]
    must equal [n_fft-cp_len, .., n_fft-1] (mod mask).  No scoreboard needed
    to spot the error on a waveform viewer.

    ConfigDB keys: n_fft, cp_len, samp_w
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        mask = (1 << samp_w) - 1

        item = CpInserterSeqItem()
        item.samples = [i & mask for i in range(n_fft)]
        item.cp_len = cp_len
        item.samp_w = samp_w
        await self.start_item(item)
        await self.finish_item(item)


class VaryingCpLenSeq(uvm_sequence):
    """
    One symbol per cp_len value in the cp_lens list, driven back-to-back.

    Models the 5G NR slot structure: symbol 0 uses the extended CP, symbols 1-13
    use the normal CP.  Exercises runtime cp_len reconfiguration between packets.

    ConfigDB keys: n_fft, samp_w, cp_lens (list[int])
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        samp_w = _cfg(self, "samp_w", 16)
        cp_lens = _cfg(self, "cp_lens", [0, 4, 8, 16])
        mask = (1 << samp_w) - 1

        for cp_len in cp_lens:
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(n_fft)]
            item.cp_len = cp_len
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)


class ZeroCpSeq(uvm_sequence):
    """
    count symbols with cp_len=0 - pure passthrough.

    Output must equal input verbatim.  Verifies the DUT drives tlast at
    beat N_FFT-1 without prepending any samples.

    ConfigDB keys: n_fft, samp_w, count
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        samp_w = _cfg(self, "samp_w", 16)
        count = _cfg(self, "count", 8)
        mask = (1 << samp_w) - 1

        for _ in range(count):
            item = CpInserterSeqItem()
            item.samples = [random.randint(0, mask) for _ in range(n_fft)]
            item.cp_len = 0
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)
